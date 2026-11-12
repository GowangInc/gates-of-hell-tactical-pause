local EXPECTED_SHA256 = "4b6a807ad867c4f6eb1019376224d74fa3a6ac048355739ab0b76d73c7c0a267"
local NOPS = string.rep(string.char(0x90), 5)
local PAUSE_REQUEST_SIGNATURE = {returns = "void", args = {"ptr", "i32"}}
local CONFIRM_SIGNATURE = {returns = "void", args = {"ptr", "i32"}}
local CONFIRMATIONS = {
	[0x2df1c0] = string.char(0x48, 0x89, 0x5c, 0x24, 0x10, 0x48, 0x89, 0x74, 0x24, 0x18),
	[0x2df480] = string.char(0x48, 0x89, 0x5c, 0x24, 0x10, 0x56, 0x48, 0x81, 0xec, 0xb0, 0, 0, 0),
}

return {
	OnLoad = function()
		-- The launcher verifies offline Steam, disabled Cloud and a loopback-only
		-- namespace before setting this flag. Ordinary launches stay unmodified.
		if os.getenv("OMP_GOH_OFFLINE_TACTICAL_PAUSE") ~= "1" then
			Ext.Log("inactive: use run_offline.py for the isolated solo session")
			return
		end
		assert(Ext.ApiVersion == 1, "unsupported GOHSE API")
		assert(Ext.Game.Process:lower() == "call_to_arms.exe", "client process required")
		assert(Ext.Game.SHA256:lower() == EXPECTED_SHA256, "unsupported game build")

		local pause_request = Ext.Game.Address(0xc725e0)
		assert(Ext.Memory.Read(pause_request, 16) ==
			string.char(0x40, 0x57, 0x48, 0x83, 0xec, 0x50, 0x48, 0x89,
				0x74, 0x24, 0x68, 0x48, 0x8b, 0xf9, 0x8b, 0xf2), "pause sender entry mismatch")

		-- Keep the native server pause/resume handshake and order queue. Exclude
		-- only eGameClient's local scene-pause owner, which locks RTS input.
		-- Skip its matching removal too; never edit the owner tree or its count.
		Ext.Memory.Patch(Ext.Game.Address(0xc73c42),
			string.char(0xe8, 0x69, 0xb1, 0x9e, 0xff), NOPS)
		Ext.Memory.Patch(Ext.Game.Address(0xc73c64),
			string.char(0xe8, 0xd7, 0xb2, 0x9e, 0xff), NOPS)

		-- Confirmed surrender/leave sends save request 0x77. First send the
		-- ordinary pause toggle (mode 0); while paused this resumes the server.
		-- Do not call its client acknowledgement handler or force a local owner.
		local function confirmed_exit(ctx, dialog, result)
			if result == 4 then -- Native dialog result: Yes, not Cancel.
				local client = Ext.Memory.ReadPointer(Ext.Game.Address(0x15a4f00))
				if client ~= Ext.Memory.Null
					and Ext.Memory.ReadU32(Ext.Memory.Add(client, 0x244)) == 1 then
					Ext.Native.Call(pause_request, PAUSE_REQUEST_SIGNATURE, client, 0)
					Ext.Log("requested Conquest resume before confirmed save/exit")
				end
			end
			return ctx.Original(dialog, result)
		end
		for rva, expected in pairs(CONFIRMATIONS) do
			local target = Ext.Game.Address(rva)
			assert(Ext.Memory.Read(target, #expected) == expected, "confirmation entry mismatch")
			Ext.Hooks.Add(target, CONFIRM_SIGNATURE, confirmed_exit)
		end
		Ext.Log("offline tactical pause active: Pause toggles; RTS orders remain enabled")
	end,
}
