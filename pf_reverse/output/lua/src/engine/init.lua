bee = bee or {}
CU = CS.UnityEngine

if not module then
    function module(modelName)
        local M = {};
        _G[modelName] = M;
        setmetatable(M, {__index = _G});
        setfenv(1, M);
    end
end

bee.pfsys = CS.Utils.GetSys()

if bee.pfsys == "android" then
    bee.isAndroid = true
elseif bee.pfsys == "ios" then
    bee.isIos = true
else
    bee.isPc = true
end
bee.isEditor = CS.Utils.IsEditor()

require "engine.ResManager"
require "engine.geometry"
require "engine.functions"
require "engine.json"
require "engine.scheduler"
require "engine.Object"
require "engine.ObjectPool"
require "engine.event"
require "engine.tween"
require "engine.spine"
require "engine.ObjectCache"
require "engine.task"
require "engine.timetrack"
require "engine.timeline"

require "sdk.SdkHelper"
require "sdk.PayHelper"
require "sdk.GoogleMgr"
require "sdk.AdHelper"
require "sdk.YiDunHelper"

require "manager.LocalStore"
require "manager.LanguageManager"
require "manager.Net"
require "manager.RedManager"
require "manager.TimeHelp"
require "manager.VibrateManager"

ObjectCache:initRoot()

local _sceneParams = nil
local _sceneName, _sceneWaitName, _sceneWaitParams = nil, nil, nil
bee.enterScene = function(name, params, sync)
    if ResManager:IsLoadingScene() then
        if _sceneName ~= name then
            _sceneWaitName, _sceneWaitParams = name, params
        else
            _sceneParams = params
        end
    else
        _sceneName, _sceneParams = name, params
        _sceneWaitName, _sceneWaitParams = nil, nil
        if sync then
            ResManager:LoadScene(name)
        else
            ResManager:LoadSceneAsync(name)
        end
    end
end

bee.on("evt_load_scene_suc", function(d)
    if _sceneWaitName then
        bee.enterScene(_sceneWaitName, _sceneWaitParams)
    end
end)

bee.getSceneParams = function(noClear)
    local ret = _sceneParams
    if not noClear then
        _sceneParams = nil
    end
    return ret
end

bee.getCurRunScene=function()
	return CU.Application.loadedLevelName
end

bee.isNull = function(obj)
    return not obj or CS.Utils.IsNull(obj)
    -- return not obj or obj:Equals(nil)
end

bee.getPrefab = function(name)
    return ResManager:GetPrefab(name .. ".prefab")
end

bee.createObj = function(name, params)
    local obj = ResManager:InstantiateObject(name .. ".prefab")
    if params then
		local cls = ObjectPool:getCls(obj)
        if cls then
            cls:setParams(params)
        end
    end
    return obj
end

bee.createPrefabObj = function(name, params)
    local prefab = bee.getPrefab(name)
    if prefab then
        local obj = CU.GameObject.Instantiate(prefab)
        if params then
            local cls = ObjectPool:getCls(obj)
            if cls then
                cls:setParams(params)
            end
        end
        return obj
    end
    return nil
end

bee.moveBy = function(obj, x, y, z, isWorld)
    local p1 = isWorld and obj.transform.position or obj.transform.localPosition
    p1.x = p1.x + (x or 0)
    p1.y = p1.y + (y or 0)
    p1.z = p1.z + (z or 0)
    if isWorld then
        obj.transform.position = p1
    else
        obj.transform.localPosition = p1
    end
end

bee.setText = function(obj, s, cmpName)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent(cmpName or "Text")
        if cmp then
            cmp.text = s
        elseif not cmpName then
            cmp = obj:GetComponent("TextMeshProUGUI")
            if cmp then
                cmp.text = s
            end
        end
    end
end

bee.setTextCut = function(obj, s, width)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent("Text")
        if cmp then
            CS.Utils.SetTextWithWidth(cmp, s, width)
        end
    end
end

bee.getText = function(obj, cmpName)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent(cmpName or "Text")
        if cmp then
            return cmp.text
        end
    end
end

bee.setFillAmount = function(obj,value)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent("Image")
        cmp.fillAmount=value
    end
end

bee.getFillAmount = function(obj)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent("Image")
        return cmp.fillAmount
    end
    return 0
end

bee.setSliderValue = function(obj,value,notHide)
	if not bee.isNull(obj) then
		local cmp = obj:GetComponent("Slider")
		cmp.value=value
        if cmp.fillRect and not notHide then
            cmp.fillRect.gameObject:SetActive(value > 0)
        end
	end
end

bee.getSliderValue = function(obj)
	if not bee.isNull(obj) then
		local cmp = obj:GetComponent("Slider")
        if cmp then
            return cmp.value
        end
	end
    return 0
end

bee.setImage = function(obj, img, fromAtlas, nativeSize)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent("Image")
        if cmp then
            local tex = nil
            if fromAtlas then
                tex = SpriteManager:GetSprite(img)
            else
                tex = SpriteManager:GetSpriteFromRes(img)
            end
            if tex then
                cmp.sprite = tex
                if fromAtlas then
                    nativeSize = nativeSize == nil and true or nativeSize
                    if nativeSize then
                        cmp:SetNativeSize()
                    end
                    -- cmp.useSpriteMesh = true
                    -- local size = bee.v2Mul(obj.transform.sizeDelta, cmp.pixelsPerUnit);
                    -- local pixelPivot = cmp.sprite.pivot;
                    -- obj.transform.pivot = bee.v2(pixelPivot.x / size.x, pixelPivot.y / size.y);
                end
                return true
            elseif bee.isEditor then
                print("[bee.setImage] not img", img, fromAtlas)
            end
        end
    end
end

--新的图集加载方式 name精灵名字  atlasName图集名字，可选参数
bee.setIcon = function(obj, name, atlasName, nativeSize)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent("Image")
        if cmp then
            local tex = nil
            if atlasName then
                if type(atlasName) == "string" then
                    tex = ResManager:GetAtlasSprite(atlasName,name)
                else
                    nativeSize = atlasName
                    tex = ResManager:GetSprite(name)
                end
            else
                tex = ResManager:GetSprite(name)
            end
            if tex then
                cmp.sprite = tex
                if nativeSize then
                    cmp:SetNativeSize()
                end
                return true
            end
        end
    end
end

bee.setIconInAtlas = function(obj, name, nativeSize)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent("Image")
        if cmp then
            local tex = ResManager:GetAtlasSpriteWithName(name)
            if tex then
                cmp.sprite = tex
				if nativeSize then
					cmp:SetNativeSize()
				end
                return true
            end
        end
    else
        print("[setIconInAtlas] obj nil ", name)
    end
end

bee.setSpriteImg = function(obj, img)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent("SpriteRenderer")
        if cmp then
            local tex = ResManager:GetAtlasSpriteWithName(img)
            if tex then
                cmp.sprite = tex
                -- if fromAtlas then
                --     cmp:SetNativeSize()
                --     cmp.useSpriteMesh = true
                --     local size = bee.v2Mul(obj.transform.sizeDelta, cmp.pixelsPerUnit);
                --     local pixelPivot = cmp.sprite.pivot;
                --     obj.transform.pivot = bee.v2(pixelPivot.x / size.x, pixelPivot.y / size.y);
                -- end
                return true
            end
        end
    end
end

bee.setSprite = function(obj, img)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent("SpriteRenderer")
        if cmp then
            local tex = ResManager:GetAtlasSpriteWithName(img)
            if tex then
                cmp.sprite = tex
                -- if fromAtlas then
                --     cmp:SetNativeSize()
                --     cmp.useSpriteMesh = true
                --     local size = bee.v2Mul(obj.transform.sizeDelta, cmp.pixelsPerUnit);
                --     local pixelPivot = cmp.sprite.pivot;
                --     obj.transform.pivot = bee.v2(pixelPivot.x / size.x, pixelPivot.y / size.y);
                -- end
                return true
            end
        end
    end
end

bee.setSpriteUrl = function(obj, url)
	if not bee.isNull(obj) then
		local cmp = obj:GetComponent("Image")
		if cmp then
			SpriteManager:LoadSpriteUrl(cmp,url)
		end
	else
		print("obj nil ",url)
	end
end

-- 根据给定的 width 或 height 等比重设 obj 的 size
bee.setAutoSize = function(obj, width, height)
    local s = obj.transform.sizeDelta
    if width then
        s.y = width / s.x * s.y
        s.x = width
        obj.transform.sizeDelta = s
    elseif height then
        s.x = height / s.y * s.x
        s.y = height
        obj.transform.sizeDelta = s
    end
end

bee.setColor = function(obj, c, cmpName)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent(cmpName or "Image")
        if cmp then
            cmp.color = c
        end
    end
end

bee.getColor = function(obj, c, cmpName)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent(cmpName or "Image")
        if cmp then
            return cmp.color
        end
    end
    return CU.Color(1, 1, 1)
end

bee.setOpacity = function(obj, op, cmpName)
    if not bee.isNull(obj) then
        local cmp = obj:GetComponent(cmpName or "Image")
        if cmp then
            cmp.color = CU.Color(cmp.color.r, cmp.color.g, cmp.color.b, op)
        end
    end
end

bee.setAlpha = function(obj, op, cmpName)
	if not bee.isNull(obj) then
		local cmp = obj:GetComponent(cmpName or "CanvasGroup")
		if cmp then
			cmp.alpha = op
		end
	end
end

bee.addClick = function(obj, callback, isRemove)
    if not bee.isNull(obj) and callback then
        local cmp = obj:GetComponent("Button")
        if cmp then
            if isRemove then
                cmp.onClick:RemoveAllListeners()
            end
            cmp.onClick:AddListener(callback)
        end
    end
end

bee.addClick2 = function(obj, callback, isRemove)
    if not bee.isNull(obj) and callback then
        local cmp = obj:GetComponent("Button")
        if cmp then
            if isRemove then
                cmp.onClick:RemoveAllListeners()
            end
            cmp.onClick:AddListener(callback)
        end
    end
end

bee.addLongClick = function(obj, callback)
    if not bee.isNull(obj) and callback then
        local cmp = obj:GetComponent("Button")
        if cmp then
            cmp.onLongClick:AddListener(callback)
        end
    end
end

bee.removeClick = function(obj, callback)
    if not bee.isNull(obj) and callback then
        obj:GetComponent("Button").onClick:RemoveListener(callback)
    end
end

bee.removeAllClick=function (obj)
    if not bee.isNull(obj)  then
        obj:GetComponent("Button").onClick:RemoveAllListeners()
        if obj:GetComponent("Button").onLongClick then
            obj:GetComponent("Button").onLongClick:RemoveAllListeners()
        end
    end
end

bee.setBtEnable=function(obj,value)
	if not bee.isNull(obj) then
		obj:GetComponent("Button").enabled = value
	end
end

bee.playAnimator = function(obj, name, layer, index)
    local animator = obj:GetComponent("Animator")
    if animator then
        animator:Play(name, layer or -1, index or 0)
    end
end

local color_gray, color_white = CU.Color(0.4, 0.4, 0.4, 1), CU.Color(1, 1, 1, 1)
bee.setGray=function(obj, isGray, cmp)
	if not bee.isNull(obj) then
		local cmp = obj:GetComponent(cmp or "Image")
        if cmp then
            if isGray then
                cmp.color = color_gray
            else
                cmp.color = color_white
            end
        end
	end
end

bee.playParticle=function(obj)
	if not bee.isNull(obj) then
		local cmp = obj:GetComponent("ParticleSystem")
		if cmp then
			cmp:Play()
		end
	end
end

bee.changeParticleColor=function(obj,colorStr)
	if not bee.isNull(obj) then
		local cmp = obj:GetComponent("ParticleSystemRenderer")
		if cmp then
		   local color=  CS.NLog.HexToColor(colorStr)			
		   cmp.material:SetColor("_MainColor",color)
		end
	end
end

bee.particleTweenColor=function(obj,colorStr)
	if not bee.isNull(obj) then
		local cmp = obj:GetComponent("ParticleSystemRenderer")
		if cmp then
			local color=  CS.NLog.HexToColor(colorStr)
			local oldColor=cmp.material:GetColor("_MainColor")
			bee.Tween.toColor(oldColor,color,0.5,function (value)
					cmp.material:SetColor("_MainColor",value)
			end)
		end
	end
end


bee.particleTweenAlpha=function(obj,from,to,time)
	if not bee.isNull(obj) then
		local cmp = obj:GetComponent("ParticleSystemRenderer")
		if cmp then
			local oldColor=cmp.material:GetColor("_MainColor")
			local fcolor=  CU.Color(oldColor.r, oldColor.g, oldColor.b, from)
			local tcolor=  CU.Color(oldColor.r, oldColor.g, oldColor.b, to)
			bee.Tween.toColor(fcolor,tcolor,time,function (value)
                if not bee.isNull(obj) then
					cmp.material:SetColor("_MainColor",value)
                end
			end)
		end
	end
end


bee.addValueChanged=function ( toggle,callback,cmpName)
    if not cmpName or cmpName == "Toggle" then
        bee.onCheck(toggle, callback)
        return
    end
    if not bee.isNull(toggle) and callback then
        toggle:GetComponent(cmpName or "Toggle").onValueChanged:AddListener(callback)
    end
end

bee.removeValueChanged=function ( toggle,cmpName )
    if not cmpName or cmpName == "Toggle" then
        bee.removeCheck(toggle)
        return
    end
    if not bee.isNull(toggle) then
        toggle:GetComponent(cmpName or "Toggle").onValueChanged:RemoveAllListeners()
    end
end

bee.onCheck = function(toggle, callback)
    if not bee.isNull(toggle) and callback then
        toggle:GetComponent("Toggle").onValueChanged:AddListener(callback)
    end
end

bee.onCheck2 = function(toggle, callback)
    if not bee.isNull(toggle) and callback then
        toggle:GetComponent("Toggle").onValueChanged:AddListener(callback)
    end
end

bee.removeCheck = function(toggle)
    if not bee.isNull(toggle) then
        toggle:GetComponent("Toggle").onValueChanged:RemoveAllListeners()
    end
end

bee.setCheck=function (toggle, notify, flag)
    if not bee.isNull(toggle) then
        if nil == flag then
            flag = true
        end
		if notify then
			toggle:GetComponent("Toggle").isOn=flag
		else
			toggle:GetComponent("Toggle"):SetIsOnWithoutNotify(flag)
		end		
    end
end

bee.setUncheck = function(toggle, notify)
    if not bee.isNull(toggle) then
		if notify then
			toggle:GetComponent("Toggle").isOn = false
		else
			toggle:GetComponent("Toggle"):SetIsOnWithoutNotify(false)
		end		
    end
end

bee.setToggleGroup = function(toggle, group)
    if not bee.isNull(toggle) then
        toggle:GetComponent("Toggle").group = group:GetComponent("ToggleGroup")
    end
end

bee.isCheck = function(toggle)
    if not bee.isNull(toggle) then
        return toggle:GetComponent("Toggle").isOn
    end
    return false
end

bee.showDropDown=function(dropDown,cmpName)
	if dropDown then
		dropDown:GetComponent(cmpName or "Dropdown"):Show()
	end
end

bee.hideDropDown=function(dropDown,cmpName)
	if dropDown then
		dropDown:GetComponent(cmpName or "Dropdown"):Hide()
	end
end

bee.clearOptions=function(dropDown,cmpName)
	if dropDown then
		dropDown:GetComponent(cmpName or "Dropdown"):ClearOptions()
	end
end

bee.addOptions=function(dropDown,options,cmpName)
	if dropDown then
		local list_String=CS.System.Collections.Generic.List(CS.System.String)
		local opLists=list_String()
		for k, v in pairs(options) do
			opLists:Add(_T(v))
		end
		dropDown:GetComponent(cmpName or "Dropdown"):ClearOptions()
		dropDown:GetComponent(cmpName or "Dropdown"):AddOptions(opLists)
	end
end

bee.setToggle=function (toggle,value)
	if toggle then
		if toggle:GetComponent("Toggle") then
			toggle:GetComponent("Toggle").isOn=value
		end
	end
end


-- 查找子物体
bee.find = function(name, parent)
    local t = nil
	if parent then
		t = parent.transform:Find(name)
	else
		t = CU.GameObject.Find(name)
	end
    if t then
        return t.gameObject
    end
	return nil
end

bee.playSound = function(name, isAsyn, volume, loop)
    loop = loop == 1 and true or false
    volume = (volume == nil or not tonumber(volume)) and 1 or volume
    if isAsyn then
        return CS.SoundManager.Instance:PlaySoundAsyn(name, loop, volume)
    else
        return CS.SoundManager.Instance:PlaySound(name, loop, volume)
    end
end

bee.stopSound = function(name)
    CS.SoundManager.Instance:StopSound(name)
end

bee.stopSoundByIndex = function(index)
    CS.SoundManager.Instance:StopSoundIndex(index)
end

bee.pauseSound = function(index)
    CS.SoundManager.Instance:PauseSoundByIndex(index)
end

bee.unPauseSound = function(index)
    CS.SoundManager.Instance:UnPauseSoundByIndex(index)
end

bee.changeSoundVolume = function(index, vol)
    if not index then
        return
    end
    vol = (vol == nil or not tonumber(vol)) and 1 or vol
    CS.SoundManager.Instance:ChangeSoundVolume(index, vol)
end

bee.playVoice = function(name, isAsyn, volume, loop)
    loop = loop == 1 and true or false
    volume = (volume == nil or not tonumber(volume)) and 1 or volume
    if isAsyn then
        return CS.SoundManager.Instance:PlayVoiceAsyn(name, loop, volume)
    else
        return CS.SoundManager.Instance:PlayVoice(name, loop, volume)
    end
end

bee.stopVoice = function(name)
    CS.SoundManager.Instance:StopVoice(name)
end

bee.changeVoiceVolume = function(index, vol)
    if not index then
        return
    end
    vol = (vol == nil or not tonumber(vol)) and 1 or vol
    CS.SoundManager.Instance:ChangeVoiceVolume(index, vol)
end

bee.playMusic = function(name, isAsyn, volume, alertDt)
    if isAsyn then
        CS.SoundManager.Instance:PlayMusicAsyn(name)
    else
        CS.SoundManager.Instance:PlayMusic(name)
    end
    if not alertDt then
        if volume then
            bee.changeMusicVolume(volume)
        end
    else
        bee.changeMusicVolume(0)
        bee.Tween.toFloat(0, volume, alertDt, function(v)
			bee.changeMusicVolume(v)
        end)
    end
end

bee.stopMusic = function()
    CS.SoundManager.Instance:StopMusic()
end

bee.changeMusicVolume = function(vol)
    vol = (vol == nil or not tonumber(vol)) and 1 or vol
    CS.SoundManager.Instance:ChangeMusicVolume(vol)
end

bee.setMixerVolume = function(name, volume)
    CS.SoundManager.Instance:SetMixerVolume(name, volume)
end

bee.openUrl = function(url)
    CS.Utils.OpenURL(url)
end

bee.gc = function()
    CS.LuaManager.GC()
	CS.System.GC.Collect()
    collectgarbage("collect")
end

-- 添加监控函数
bee.lookFunc = function(cb)
    if cb then
        if not bee._weakCbs then
            bee._weakCbs = {}
            setmetatable(bee._weakCbs, {__mode = "k"})
        end
        bee._weakCbs[cb] = os.time()
    end
    return cb
end

bee.printLookFunc = function()
    if bee._weakCbs then
        local tbr = {}
        for k, v in pairs(bee._weakCbs) do
            tbr[#tbr + 1] = {v, k}
        end
        table.sort(tbr, function(a, b) return a[1] < b[1] end)
        for _, v in ipairs(tbr) do
            print("[bee] in use function", v[1], v[2])
        end
    end
end

bee.checkCd = function(tag, cd)
    if not bee._checkCds then
        bee._checkCds = {[tag] = scheduler.timeSpend}
        return true
    end
    local old, now = bee._checkCds[tag], scheduler.timeSpend
    if not old or (now ~= old and math.abs(now - old) >= (cd or 3)) then
        bee._checkCds[tag] = now
        return true
    end
    return false
end

bee.randomseed = function(seed)
	CS.Utils.SetRandomseed(seed)
end

bee.random = function(min, max)
    if not min and not max then
        return math.random()
    end
    if not max then
        if min <= 1 then
            return min
        end
        return CS.Utils.Random(1, min + 1)
    end
    return CS.Utils.Random(min, max + 1)
end

--bool = true 置灰  = false 恢复正常
--destroy时调用false 将缓存材质置空
local cacheMaterials = {}
bee.setGrey = function(gameObject, bool, notTex)
    if bee.isNull(gameObject) then
        return
    end
    local images = gameObject.transform:GetComponentsInChildren(typeof(CU.UI.Image))
    local texts = gameObject.transform:GetComponentsInChildren(typeof(CU.UI.Text))
    
    if bool then
        if not cacheMaterials[gameObject] then
            cacheMaterials[gameObject] = {}
        end
        local materials = cacheMaterials[gameObject]
        local material = nil
        local greyMat = ResManager:GetMaterial("material/UIGray.mat")
        for i = 0, images.Length - 1 do
            material = images[i].material
            if not materials[images[i]] then
                materials[images[i]] = material
            end
            images[i].material = greyMat
        end
        if not notTex then
            for i = 0, texts.Length - 1 do
                material = texts[i].material
                if not materials[texts[i]] then
                    materials[texts[i]] = material
                end
                texts[i].material = greyMat
            end
        end
    else
        local materials = cacheMaterials[gameObject]
        if not materials or table.nums(materials) <= 0 then
            return
        end
        for i = 0, images.Length - 1 do
            images[i].material = materials[images[i]]
        end
        if not notTex then
            for i = 0, texts.Length - 1 do
                texts[i].material = materials[texts[i]]
            end
        end
        cacheMaterials[gameObject] = nil
    end
end


bee.getDownloadImage = function (obj, url)
    if not bee.checkVersion("1.4.6") then
        obj:GetComponent("LoadImage"):DownloadImage(url)
    else
        local pathPart = string.match(url, "^https?://[^/]+(/.+)$")
        local nurl = ""
        if pathPart then
            local parts = {}
            for segment in string.gmatch(pathPart:sub(2), "([^/]+)") do
                table.insert(parts, segment)
            end
            
            local remoteIndex = LocalStore:getIntegerForKey("remote_host_index", 1)
            nurl = _G["G_RES_BASE_HOST" .. remoteIndex] or G_RES_BASE_HOST
            for _,v in ipairs(parts) do
                nurl = nurl .. "/" .. v
            end
        end
        obj:GetComponent("LoadImage"):DownloadImages({nurl, url})
    end
end

-- bee.setHollow = function(gameObject, bool, pos, size)
--     if bee.isNull(gameObject) then
--         return
--     end

--     if bool then
--         local image = gameObject.transform:GetComponent("Image")
--         local hollowMat = image.material
--         if hollowMat == nil or hollowMat.name == "Default UI Material" then
--             hollowMat = ResManager:GetNewMaterial("Custom/UIHollowRect")
--             image.material = hollowMat
--         end
--         hollowMat:SetVector("_CenterWorld", CU.Vector4(pos.x, pos.y, 0, 0))
--         hollowMat:SetFloat("_WidthPixels", size[1])
--         hollowMat:SetFloat("_HeightPixels", size[2])
--         local rectTran = UiManager:getUiRoot():GetComponent("RectTransform")
--         hollowMat:SetVector("_Ratio", CU.Vector4(rectTran.sizeDelta.x, rectTran.sizeDelta.y, 0, 0))
--     else
--         local image = gameObject.transform:GetComponent("Image")
--         image.material = nil
--     end
-- end