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
		local function read_marker(path)
			if io == nil or io.open == nil then
				return nil
			end
			local open_ok, file = pcall(io.open, path, "r")
			if not open_ok or file == nil then
				return nil
			end
			local read_ok, content = pcall(function() return file:read("*a") end)
			pcall(function() file:close() end)
			if not read_ok then
				return nil
			end
			return content
		end

		local source = debug.getinfo(1, "S").source
		local script_path = source:sub(1, 1) == "@" and source:sub(2) or source
		local mod_root = script_path:gsub("[/\\]resource[/\\]script[/\\]gohse[/\\]bootstrap%.lua$", "")
		local marker_hash = read_marker(mod_root .. "/enable-tactical-pause")
		if marker_hash == nil then
			-- Marker missing/unreadable or sandboxed io: the documented env
			-- fallback still requires the exact build hash, so this stays
			-- fail-closed.
			marker_hash = os.getenv("OMP_GOH_ENABLE_TACTICAL_PAUSE")
		end
		if marker_hash == nil then
			Ext.Log("inert: enable-tactical-pause marker unreadable and no OMP_GOH_ENABLE_TACTICAL_PAUSE fallback")
			return
		end
		marker_hash = marker_hash:match("^%s*(.-)%s*$")
		if marker_hash:lower() ~= Ext.Game.SHA256:lower() then
			Ext.Log("inert: marker build hash mismatch")
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
		Ext.Log("tactical pause 0.5.0 active: Pause toggles; RTS orders remain enabled")
	end,
}
