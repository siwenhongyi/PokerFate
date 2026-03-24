local P = class("StartScene", UiScene)

function P:ctor()
    print("start scene =====")
    self.isLoginSuc = false
    UiManager:resetScreenMatch()
	bee.clearFontCache()
	-- self:addAutoEvent()
	--CS.ResManager.Instance:PreLoadAllAssets()

	-- if bee.checkVersion("1.4.1") and CS.SdkHelper.CheckIsEmulator() then
	-- 	return
	-- end

	-- UiManager:showUI("views/Login/AppStartLayer")
	UiManager:showUI("LoginStartLayer")
	
	bee.once(0.1, function()
		refreshScreenSize()
		UiManager:resetScreenMatch()
    	Game:stopRoleSound()
	end)

	Game:stopMusic()

    UiManager:showUI("views/GMLayer")
	ObjectCache:clearAll()
	
	local params = bee.getSceneParams()
	if params and params.onEnter then
		params.onEnter()
	end
end

function P:onEnter()
	P.super.onEnter(self)
	-- print("=====g CS.AppLoader.isOpen ",CS.AppLoader.isOpen,CS.AppLoader.isReload)
    -- if CS.AppLoader.isOpen and not CS.AppLoader.isReload and false then
    --     if not AppLoadRes:checkUpdate(false) then
	-- 		self:evt_updateFinish()
	-- 	end
    -- else
	-- 	require("app.init")
    --     self:evt_loadDefautlAssetsDone()--暂时不做预加载
    -- end
end

function P:onExit()
	P.super.onExit(self)
end

-- function P:evt_updateFinish()
-- 	require("app.init")
--     self:evt_loadDefautlAssetsDone()
-- end

return P
