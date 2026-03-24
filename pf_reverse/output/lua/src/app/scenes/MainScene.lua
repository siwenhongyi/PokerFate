---@class MainScene
require "app.init"
local P = class("MainScene", UiScene)

function P:ctor()
	print("MainScene =====")
	UiManager:resetScreenMatch()
	UiManager.sortingIndex = 0
	CU.Time.timeScale = 1
	bee.clearFontCache()
	
	--if Config.IS_HIGH_MEMORY then
		SpriteManager:RemoveAll()
		ResManager:ReleaseHandles()
	--end

	local params = bee.getSceneParams()
	if params and params.onEnter then
		params.onEnter()
	else
		UiManager:showUI("LobbyLayer", params)
	end
	if not params or params.from ~= "StartScene" then
		if PlayerModel:isLogin() then
			NoticeModel:reqNoticeList()
			EmailModel:reqEmailNum()
		end
	end

	if params and params.info then
		if params.info.key == "tournament" then
			UiManager:showUI("TournamentLobby", {kind = params.info.kind})
		end
	end

	if params then
		if params.afterShow then
			params.afterShow()
		end
	end
	
	--if Config.IS_HIGH_MEMORY then
		ResManager:UnloadUnusedAssets()
		bee.gc()
	--end
	
	-- bee.stopMusic()
	bee.stopSound()
	-- Game:playLobbyBGM()

	-- UiManager:showUI("GMLayer")

	bee.emit("evt_EnterMainScene")

	bee.log("game-load")

    UiManager:showUI("views/GMLayer")

	CS.SdkHelper.setScreenSleep(true)
end

function P:onEnter()
    P.super.onEnter(self)
	if not PlayerModel:isLogin() then
		bee.enterScene("StartScene")
	else
	end
end

function P:onExit()
    P.super.onExit(self)
	bee.removeAllTasks()
end

function P:evt_onApplicationPause(paused)
    if not paused then
		Net:showWaitNet()
        if Net:isConnected() then
			Net:sendReq("pb.HeartBeatREQ", {})
			Net:sendReq("pb.GetServerTimeREQ", {})
			GF.dealDeepLinkParams()
			LoginModel:checkLoginValid()
		elseif PlayerModel:isLogin() then
			LoginModel:checkLoginValid(function()
				LoginModel:reConnectWithCheck()
			end)
		end
    end
end

return P
