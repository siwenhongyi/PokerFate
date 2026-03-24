--print("===== load main.lua =====", jit)
if jit and jit.off then
    jit.off()
    print("off jit ")
end

CS.SdkHelper.InitGame()
require "engine.init"
require "app.Constants"
require "manager.LogTool"
require "ui.init"
require "net.init"
print("main.lua isOpen",CS.AppLoader.isOpen,"isReload ",CS.AppLoader.isReload)
--if not CS.AppLoader.isOpen or CS.AppLoader.isReload then
    require "app.init"
--end

--if CS.AppLoader.isOpen then
    require "appload.AppLoadRes"
--end

SdkHelper.adjustLaunched()
LogTool:init()

if bee.isEditor then
	local _, LuaDebuggee = pcall(require, 'LuaDebuggee')
	if LuaDebuggee and LuaDebuggee.StartDebug then
		if LuaDebuggee.StartDebug('127.0.0.1', 9826) then
			print('LuaPerfect: Successfully connected to debugger!')
		else
			print('LuaPerfect: Failed to connect debugger!')
		end
	else
		print('LuaPerfect: Check documents at: https://luaperfect.net')
	end
end
