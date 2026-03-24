local P = class("LoadingScene", UiScene)

function P:ctor()
	bee.Spine.clearAll()
	--if not Config.IS_HIGH_MEMORY then
		SpriteManager:RemoveAll()
		ResManager:ReleaseHandles()
	--end
	ResManager:UnloadUnusedAssets()
	bee.gc()
	
	bee.stopMusic()

	UiManager:resetScreenMatch()
	print("LoadingScene =====",params)

	UiManager:showUI("views/Main/LoadingUI")
end

return P
