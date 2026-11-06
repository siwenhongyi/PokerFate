-- 工具类，方向直接附加到 bee
bee = bee or {}

function bee.isInStart()
	return "StartScene" == bee.getCurRunScene()
end

function bee.isInGame()
	return "GameScene" == bee.getCurRunScene()
end

function bee.isInHome()
	return "MainScene" == bee.getCurRunScene()
end

-- 获取奖励列表
function bee.getBoxItems(boxId)
	local d = tpl_prop[boxId]
	local items = {}
	if d and d.items then
		for i = 1, #d.items - 1, 2 do
			table.insert(items, {id = d.items[i], count = d.items[i + 1]})
		end
	end
	return items
end

function bee.getListItems(list)
	local items = {}
	for i = 1, #list - 1, 2 do
		local d = tpl_prop[list[i]]
		if d then
			if d.kind == GPropType.Box then
				local boxes = bee.getBoxItems(list[i])
				for _, v in ipairs(boxes) do
					table.insert(items, v)
				end
			else
				table.insert(items, {id = list[i], count = list[i + 1]})
			end
		end
	end
	return items
end

-- 获取 list 中随机权重值，{{val, weight}, ...}
function bee.getRateVal(list)
    local sum = 0
    for _, v in ipairs(list) do
        sum = sum + v[2]
    end
    if sum > 0 then
        local r = math.random(sum)
        for _, v in ipairs(list) do
            if r <= v[2] then
                return v[1]
            end
            r = r - v[2]
        end
    end
    return 0
end

function bee.refreshSortingOrder(node)
	local canvas = node.transform:GetComponentInParent(typeof(CS.UnityEngine.Canvas))
	local sortingOrderVal = canvas and canvas.sortingOrder or 1

	-- 刷新子节点Canvas层级
	local canvasList = node.transform:GetComponentsInChildren(typeof(CS.UnityEngine.Canvas), true)
	for i = 0, canvasList.Length - 1 do
		canvasList[i].sortingLayerName = "UI"
		canvasList[i].sortingOrder = canvasList[i].sortingOrder + sortingOrderVal
	end

	-- 子节点Renderer层级
	local rendererList = node.transform:GetComponentsInChildren(typeof(CS.UnityEngine.ParticleSystemRenderer), true)
	for i = 0, rendererList.Length - 1 do
		rendererList[i].sortingLayerName = "UI"
		rendererList[i].sortingOrder = rendererList[i].sortingOrder + sortingOrderVal
	end
end

function bee.setSortingOrder(node, sortingOrderVal)
	if not sortingOrderVal then
		return
	end

	local canvas = node.transform:GetComponent(typeof(CU.Canvas))
	if bee.isNull(canvas) then
		canvas = node:AddComponent(typeof(CU.Canvas))
		node:AddComponent(typeof(CU.UI.GraphicRaycaster))
	end

	canvas.overrideSorting = true
	canvas.sortingLayerName = "UI"
	canvas.sortingOrder = sortingOrderVal

	-- 刷新子节点Canvas层级
	local canvasList = node.transform:GetComponentsInChildren(typeof(CS.UnityEngine.Canvas), true)
	for i = 0, canvasList.Length - 1 do
		canvasList[i].sortingLayerName = "UI"
		canvasList[i].sortingOrder = sortingOrderVal
	end

	-- 子节点Renderer层级
	local rendererList = node.transform:GetComponentsInChildren(typeof(CS.UnityEngine.ParticleSystemRenderer), true)
	for i = 0, rendererList.Length - 1 do
		rendererList[i].sortingLayerName = "UI"
		rendererList[i].sortingOrder = rendererList[i].sortingOrder + sortingOrderVal
	end
end

bee.getServerTime = function(addTimeZone) 
	return LoginModel and LoginModel:getServerTime(addTimeZone) or os.time()
end

function bee.getShortNumber(num, show_sigh)
	if not num then
		return num
	end
	local ret = string.getBigNumStr(num)
	if num > 0 and show_sigh then
		ret = "+" .. ret
	end
	return ret
end

function bee.getShortNumber1(num, show_sigh)
	local ret = string.getBigNumStr1(num)
	if num > 0 and show_sigh then
		ret = "+" .. ret
	end
	return ret
end

function bee.getShortNumber2(num, show_sigh)
	local ret = string.getBigNumStr2(num)
	if num > 0 and show_sigh then
		ret = "+" .. ret
	end
	return ret
end

function bee.getColorText(text, color)
	return string.format("<color=%s>%s</color>", color or "#60616E", text or "")
end

-- 对比两个版本号 ver1 > ver2 返回 1, ver1 < ver2 返回 -1, ver1 == ver2 返回 0
bee.compareVer = function(ver1, ver2)
	local ver1s= string.split(ver1,".")
	local ver2s= string.split(ver2,".")
	for k, v in ipairs(ver1s) do
		if tonumber(v) < tonumber(ver2s[k]) then
			return -1
		elseif tonumber(v) > tonumber(ver2s[k])  then
			return 1
		end
	end
	return 0
end

-- 检查整包版本号是否大于等于 version
bee.checkVersion = function(version)
	return bee.compareVer(CU.Application.version, version) >= 0
end

bee.convertMaskToSoftMask = function(obj)
	if not bee.checkVersion("1.1.6") then
		return
	end
	
	local cmp = obj:GetComponent(typeof(CS.Coffee.UIExtensions.SoftMask))
	if bee.isNull(cmp) then
		cmp = obj:GetComponent(typeof(CU.UI.Mask))
		if not bee.isNull(cmp) then
			CU.GameObject.DestroyImmediate(cmp)
		end
		cmp = obj:AddComponent(typeof(CS.Coffee.UIExtensions.SoftMask))
		cmp.showMaskGraphic = false

		for i = 0, obj.transform.childCount - 1 do
			local rendererList = obj.transform:GetChild(i):GetComponentsInChildren(typeof(CU.UI.MaskableGraphic))
			for i = 0, rendererList.Length - 1 do
				local cmp1 = rendererList[i].gameObject:AddComponent(typeof(CS.Coffee.UIExtensions.SoftMaskable))
				cmp1.useStencil = true
			end
		end
	end
end

-- 获取限制显示的资源，isDefaultLimit: 是否默认使用限制资源
bee.getLimitViewRes = function(name, isDefaultLimit)
	local d = tpl_limitview[name]
	if not d then
		local sname = name
		local ns = string.split(sname, "/")
		if #ns > 1 then
			sname = ns[#ns]
			ns = string.split(sname, ".")
			if #ns > 1 then
				sname = ns[1]
			end
			d = tpl_limitview[sname]
		end
	end
	if d then
		if d.avenues then
			for _, v in ipairs(d.avenues) do
				if v == G_CHNL_ID then
					return d.path2
				end
			end
		end
		if bee.isLimitView then
			return d.path2
		end
		if isDefaultLimit and LocalStore:getBoolForKey("pf_limit_view", true) then
			return d.path2
		end
		return d.path1
	end
	return name
end

bee.setLimitViewIcon = function(obj, name, atlasName, nativeSize)
	bee.setIcon(obj, bee.getLimitViewRes(name), atlasName, nativeSize)
end

bee.checkInputField = function(inputItem, title, maxCount, isPassword)
	if bee.checkVersion("1.6.4") and G_CHNL_ID == 4 then
		local inputField = inputItem:GetComponent("InputField")
		local inputEx = inputItem:GetComponent("UiInputFieldEx")
		
		if inputEx then
			inputEx.onPointerDown = function ()
				local SII = CS.SteamInputField.Instance
				if SII then
					local str = bee.getText(inputItem, "InputField")
					SII:OpenSteamKeyboard(inputField, title, str, maxCount or 99, isPassword or false)
				else
					inputField:ActivateInputField()
				end
			end
		end
	end
end

_N = bee.getShortNumber2
_N1 = bee.getShortNumber1
_N2 = bee.getShortNumber2