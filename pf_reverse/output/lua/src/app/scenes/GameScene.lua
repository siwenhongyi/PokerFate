require "app.init"

local P = class("GameScene", UiScene)

function P:ctor()
    print("GameScene =====")
	self._inBlurs = {}

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
	end
	
	--if Config.IS_HIGH_MEMORY then
		ResManager:UnloadUnusedAssets()
		bee.gc()
	--end
	
	-- bee.stopMusic()
	bee.stopSound()
	Game:playIngameBGM()

    UiManager:showUI("views/GMLayer")
	
	CS.SdkHelper.setScreenSleep(false)
end

function P:onEnter()
    P.super.onEnter(self)
end

function P:onExit()
    P.super.onExit(self)
end

function P:evt_gameBlur(flag, name)
    if flag then
		if not next(self._inBlurs) then
			local camera = bee.find("UIRoot/CameraRoot/BgCameraDepth[-2]")
			if bee.isNull(camera) then
				return
			end
			local layer = camera:GetComponent("PostProcessLayer")
			local volume = camera:GetComponent("PostProcessVolume")
			if layer and volume then
				layer.enabled = true
				volume.enabled = true
			end
		end
        self._inBlurs[name] = name
    else
        self._inBlurs[name] = nil
		if not next(self._inBlurs) then
			local camera = bee.find("UIRoot/CameraRoot/BgCameraDepth[-2]")
			if bee.isNull(camera) then
				return
			end
			local layer = camera:GetComponent("PostProcessLayer")
			local volume = camera:GetComponent("PostProcessVolume")
			if layer and volume then
				layer.enabled = false
				volume.enabled = false
			end
		end
    end
end

function P:evt_onApplicationPause(paused)
    if not paused then
		Net:showWaitNet()
		-- if self._sleepTime and math.abs(self._sleepTime - os.time()) >= 5 then
		-- 	Net:closeSocket()
		-- end
        if Net:isConnected() then
			if not GuideManager:isInGuide() and not GameModel:isStopLeaveRoom() then
				if GameModel.data then
					if not GameModel.data:isRecord() then
						GameModel:reqGetRoomDataREQ()
					end
					GF.dealDeepLinkParams()
				else
					bee.enterScene("MainScene")
				end
			end
			Net:sendReq("pb.GetServerTimeREQ", {})
			LoginModel:checkLoginValid()
		elseif PlayerModel:isLogin() then
			LoginModel:checkLoginValid(function()
				LoginModel:reConnect()
			end)
		end
	else
		-- self._sleepTime = os.time()
    end
end

return P
