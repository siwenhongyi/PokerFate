local P = {
	_uiList = {},		-- ui 列表
	_uiStack = {},		-- ui 栈
	_resHandles = {},	-- 资源句柄
	curUi = nil,
	sortingIndex = 1,	-- canvas 排序序号

	_ui_config = nil,	-- ui 的配置表 {key = name, view = prefab, src = lua, adapt = 是否自适配}
}
UiManager = P

function P:clear()
	self._uiList = {}
	self._uiStack = {}
	self._resHandles = {}
	self.curUi = nil
	self.target = nil 	-- 响应 ui 的对象
	self.clsName = nil
	self.sortingIndex = 1

	self.screenMatchValue = 0
end

function P:setUiConfig(cfg)
	self._ui_config = cfg
end

function P:bindCurUi(clsName)
	if self.curUi then
		local node = self.curUi
		clsName = clsName or self.clsName
		local cfg = nil
		if clsName == "PKTable3D" then
			if GameModel.data and GameModel.data:isSNG() and not GameModel.data:isRecord() then
				clsName = "PKTable3DSNG"
			end
		end
		if self._ui_config and self._ui_config[clsName] then
			cfg = self._ui_config[clsName]
			clsName = self._ui_config[clsName].src
		end
		
		local _, err = pcall(function()
			local cls = require(clsName)
			if cls then
				local params = ObjectPool:getBindParams()
				local c = cls:create(params)
				if cfg then
					if cfg.adapt then
						c._autoAdapt = true
					end
				end
				c.node = node
                c.transform = node.transform
				ObjectPool:bindObj(node, c)
			end
		end)
		if err then
			printError("[UiManager] bindCurUi error", clsName, err)
		end
	end
end

function P:bindObjToUi()
	if self.curUi and self._bindObj then
		local c = ObjectPool:getCls(self.curUi)
		if c then
			c:addUi(self._bindObj)
			self._bindObj = nil
		end
	end
end

function P:onAwake()
	if self.curUi then
		local c = ObjectPool:getCls(self.curUi)
		if c and c.onAdapt then c:onAdapt() end
		if c and c.onAwake then  c:onAwake() end
	end
end

function P:onStart()
	if self.curUi then
		local c = ObjectPool:getCls(self.curUi)
		if c and not bee.isNull(c.node) then
			c._watiStart = false
			if c.addAutoEvent then c:addAutoEvent() end
			if c.onStart then c:onStart() end
			if c._doShow then c:_doShow() end
		end
	end
end

function P:onDestroy()
	if self.curUi then
		local node = self.curUi
		local c = ObjectPool:getCls(node)
		if c then
			if c.removeAutoEvent then c:removeAutoEvent() end
			if c._doHide then c:_doHide() end
			if c.onDestroy then c:onDestroy() end
			c.node = nil
			ObjectPool:unbindObj(node)
		end
		for k, v in pairs(self._uiList) do
			if v.node == node then
				self._uiList[k] = nil
				break
			end
		end
		for k, v in pairs(self._uiStack) do
			if v.node == node then
				table.remove(self._uiStack, k)
				break
			end
		end
		if self.curUi == node then
			self.curUi = nil
		end
	end
end

-- 响应按钮点击，第1个参数为按钮物体
function P:onLuaClick(name, d1, d2)
	if self.curUi then
		local ui = ObjectPool:getCls(self.curUi)
		if ui and ui[name] then ui[name](ui, self.target, d1, d2) end
	end
end

function P:invoke(funcName)
	if self[funcName] then
		self[funcName](self)
	end
end

function P:showScene(name)
	if name then
		local scene = require("app.scenes." .. name);
		if scene then
			if bee.curScene then
			bee.curScene:onExit();
			end
			bee.curScene = scene:create();
			bee.curScene:onEnter();
		end
	end
end

function P:getUiRoot()
	return CS.GameMain.Instance.uiCanvas
end

function P:getPopRoot()
	return CS.GameMain.Instance.popCanvas
end

function P:getMainRoot()
	return CS.GameMain.Instance.bgCanvas
end

function P:getLobbyRoot()
	return CS.GameMain.Instance.lobbyCanvas
end

function P:get3DUIRoot()
	return CU.GameObject.Find("3DUIRoot")
end

function P:getRTCamaresRoot()
	--local HeroPool=self:getHeroPoolNode()
	return CU.GameObject.Find("RTCamareList")
end


function P:setScreenMatchValue(val)
	self.screenMatchValue = val
end

function P:getScreenMatchValue()
	return self.screenMatchValue
end

function P:resetScreenMatch()
	self:_resetScreenMatch(self:getUiRoot())
	self:_resetScreenMatch(self:getPopRoot())
	self:_resetScreenMatch(self:getMainRoot())

	local root = bee.find("UIRoot/UiCanvaPost")
	if root then
		self:_resetScreenMatch(root)
	end
end

function P:setResolution(w, h)
	self._resolutionWidth,self._resolutionHeight = w, h
	CU.Screen.SetResolution(w, h, true)
end

function P:refreshResolution()
	if self._resolutionWidth and self._resolutionHeight then
		CU.Screen.SetResolution(self._resolutionWidth, self._resolutionHeight, true)
	end
end

function P:resizeBuffers(scaleW, scaleH)
	CS.UiManager.ResizeBuffers(scaleW, scaleH);
end

function P:_resetScreenMatch(canvas)
	if canvas and self.screenMatchValue then
		local cmp = canvas:GetComponent("CanvasScaler")
		if cmp then
			cmp.matchWidthOrHeight = self.screenMatchValue
		end
	end
end

function P:_showUI(obj, uiName, params)
	if obj then
		local ui = obj
		ui.name = uiName
		local cls = ObjectPool:getCls(ui)
		if cls then
			cls.uiName = uiName
			cls:setParams(params)
			self._uiList[uiName] = {node = ui, cls = cls}

			local root, canvasFlag = params and params.parent, false
			if bee.isNull(root) then
				if (params and params.inMain) or cls.inMain then
					root = self:getMainRoot()
				elseif (params and params.inLobby) or cls.inLobby then
					root = self:getLobbyRoot()
				elseif (params and params.inPop) or cls.inPop then
					root = self:getPopRoot()
					if bee.isEditor then
						if bee.existTask()  then
							if (not params or not params.fromTask) and uiName ~= "GMLayer" and uiName ~= "MainLockTouch" then
								printError("打开窗口"..uiName.."时发现队列里面有任务执行中")
							end
						end
					end
				else
					root = self:getUiRoot()
					canvasFlag = true
				end
				self._uiStack[#self._uiStack + 1] = self._uiList[uiName]
			end
			if not bee.isRelease then
				print("[UiManager] show ui ", uiName)
			end
			ui.transform:SetParent(root.transform, false)
			if canvasFlag then
				cls.zOrder = self:_refreshCanvas(ui, nil, params and params.zOrder)
			end

			bee.emit("evt_uiManagerShowUI", uiName)
			if bee.isEditor then
				cls.__from = "T:" .. os.time() .. " " .. debug.traceback()
			end
			return cls
		else
			-- print("[UiManager showUI] error no cls name ", uiName)
		end
	else
		printError("[UiManager showUI] error no name ", uiName)
	end
end

function P:_refreshCanvas(ui, noCreate, zOrder)
	local canvas = ui:GetComponent("Canvas")
	if bee.isNull(canvas) and not noCreate then
		canvas = ui:AddComponent(typeof(CU.Canvas))
		ui:AddComponent(typeof(CU.UI.GraphicRaycaster))
		if not bee.isNull(canvas) then
			canvas.overrideSorting = true
			canvas.sortingLayerName = "UI"
		end
	end
	if not bee.isNull(canvas) then
		canvas.overrideSorting = true
		canvas.sortingLayerName = "UI"
		if not zOrder then
			local sortingOrderVal = self.sortingIndex * 20
			self.sortingIndex = self.sortingIndex + 1
			zOrder = sortingOrderVal
		end
		canvas.sortingOrder = zOrder

		-- 刷新子节点Canvas层级
		local canvasList = ui.transform:GetComponentsInChildren(typeof(CS.UnityEngine.Canvas), true)
		for i = 1, canvasList.Length - 1 do
			canvasList[i].sortingLayerName = "UI"
			canvasList[i].sortingOrder = canvasList[i].sortingOrder + zOrder
		end

		-- 子节点Renderer层级
		local rendererList = ui.transform:GetComponentsInChildren(typeof(CS.UnityEngine.ParticleSystemRenderer), true)
		for i = 0, rendererList.Length - 1 do
			rendererList[i].sortingLayerName = "UI"
			rendererList[i].sortingOrder = rendererList[i].sortingOrder + zOrder
		end
	end
	return zOrder
end

-- 显示 ui，params.inMain: 是否显示在主相机下（非ui）
function P:showUI(uiName, params)
	if bee.isNull(CS.GameMain.Instance) then return end
	
	if not params or not params.multi then
		local ui = self._uiList[uiName]
		if ui and not ui.cls.multi then
			if bee.isNull(ui.node) then
				self._uiList[uiName] = nil
			else
				ui.cls.zOrder = self:_refreshCanvas(ui.node, true, params and params.zOrder)
				ui.node.transform:SetAsLastSibling()
				ui.node:SetActive(true)
				if ui.cls.setParams then ui.cls:setParams(params) end
				if ui.cls._doShow then ui.cls:_doShow() end
				return ui.cls
			end
		end
	end
	local viewName = uiName
	if self._ui_config and self._ui_config[uiName] then
		viewName = self._ui_config[uiName].view
	end

	local obj = bee.createObj(viewName)
	return self:_showUI(obj, uiName, params)
end

function P:createUI(uiName, params)
	local viewName = uiName
	if self._ui_config and self._ui_config[uiName] then
		viewName = self._ui_config[uiName].view
	end
	local obj = nil
	if params and params.isEditor then
		obj = ResManager:GetGameObjectInEditor(viewName)
	else
		obj = bee.createObj(viewName)
	end
	if obj then
		obj.name = uiName
		local cls = ObjectPool:getCls(obj)
		if cls then
			cls.uiName = uiName
			cls:setParams(params)
		end
		if params and params.parent then
			obj.transform:SetParent(params.parent, false)
		end
	end
	return obj
end

function P:showUIAsyn(uiName, params)
	if not params or not params.multi then
		local ui = self._uiList[uiName]
		if ui then
			if bee.isNull(ui.node) then
				self._uiList[uiName] = nil
			else
				ui.node.transform:SetAsLastSibling()
				ui.node:SetActive(true)
				if ui.cls.setParams then ui.cls:setParams(params) end
				if ui.cls._doShow then ui.cls:_doShow() end
				return ui.cls
			end
		end
	end

	local viewName = uiName
	if self._ui_config and self._ui_config[uiName] then
		viewName = self._ui_config[uiName].view
	end
	
	ResManager:InstantiateObjectAsyn(viewName .. ".prefab", function(obj)
		if obj then
			self:_showUI(obj, uiName, params)
		end
	end)
	return nil
end

-- 在编辑器下显示 ui
function P:showUIatEditor(uiName, params)
	local viewName = uiName
	if self._ui_config and self._ui_config[uiName] then
		viewName = self._ui_config[uiName].view
	end
	local obj = ResManager:GetGameObjectInEditor(viewName)
	return self:_showUI(obj, uiName, params)
end

function P:hideUI(uiName)
	if self._uiList[uiName] then
		local ui = self._uiList[uiName]
		self._uiList[uiName] = nil

		for k, v in pairs(self._uiStack) do
			if v == ui then
				table.remove(self._uiStack, k)
				break
			end
		end

		ui.cls:hideUI()
		-- CU.GameObject.Destroy(ui.node)
		bee.emit("evt_uiManagerHideUI", uiName)
	end
end

function P:hideUIByCls(cls, dt)
	local ui = self._uiList[cls.uiName]
	if ui and cls == ui.cls then
		self._uiList[cls.uiName] = nil

		for k, v in pairs(self._uiStack) do
			if v == ui then
				table.remove(self._uiStack, k)
				break
			end
		end
	end
	if dt then
		CU.GameObject.Destroy(cls.node, dt)
	else
		CU.GameObject.Destroy(cls.node)
	end
	bee.emit("evt_uiManagerHideUI", cls.uiName)
end

function P:hideUIForce(uiName)
	if self._uiList[uiName] then
		local ui = self._uiList[uiName]
		self._uiList[uiName] = nil

		for k, v in pairs(self._uiStack) do
			if v == ui then
				table.remove(self._uiStack, k)
				break
			end
		end

		ui.cls:hideUIForce()
		-- CU.GameObject.Destroy(ui.node)
		bee.emit("evt_uiManagerHideUI", uiName)
	end
end

function P:hideAllUI(except_dict)
	local hide_dict = {}
	if except_dict then
		for _, v in ipairs(except_dict) do
			except_dict[v] = true
		end
	end
	for _, v in pairs(self._uiStack) do
		if not except_dict or not except_dict[v.cls.uiName] then
			hide_dict[v.cls.uiName] = true
		end
	end
	for k, v in pairs(hide_dict) do
		self:hideUI(k)
	end
end

function P:getUI(uiName)
	local ui = self._uiList[uiName]
	if ui and bee.isNull(ui.node) then
		self._uiList[uiName] = nil
		ui = nil
	end
	return ui and ui.cls
end

function P:getUiStack()
	return self._uiStack
end

function P:isTopUI(node)
	if #self._uiStack > 0 then
		for i = #self._uiStack, 1, -1 do
			local topUi = self._uiStack[i]
			if not topUi.cls.inPop then
				return topUi.node == node or topUi.cls.uiName == node
			end
		end
	end
	return false
end

function P:showToast(text, pos, force, isSilence)
	local view = self:getUI("views/Toast")
    if view then
		self:hideUI("views/Toast")
	end
	self:showUI("views/Toast", {text = text, pos = pos, isForce = force, isSilence = isSilence})
end

function P:showError(text, isSilence)
	self:showUI("views/Toast", {text = text, isSilence = isSilence})
end

-- 显示提示框
-- text: 提示内容
-- button: 按钮数量，默认 2
-- onSure: 确认回调
-- onCancel: 取消回调
function P:showTip(params)
	-- self:showUI("TipDialog", params)
	if params.style == "big" then
		return self:showUI("CommonNotice", params)
	end
	if params.button == 1 then
		return self:showUI("CommonNoticeSmall2", params)
	end
	return self:showUI("CommonNoticeSmall", params)
end

function P:showLoadingMask(name, tip)
	local ui = self:getUI("LoadingMask")
	if not ui then
		ui = self:showUI("LoadingMask")
	end
	if ui then
		ui:addTag(name or "default", tip)
	end
end

function P:hideLoadingMask(name)
	local ui = self:getUI("LoadingMask")
	if ui then
		ui:removeTag(name or "default")
	end
end

function P:hideLoadingMaskAll()
	local ui = self:getUI("LoadingMask")
	if ui then
		UiManager:hideUI("LoadingMask")
	end
end

function P:releaseResHandles()
	-- for k, _ in pairs(self._resHandles) do
	-- 	ResManager:ReleaseHandleByName(k .. ".prefab")
	-- 	self._resHandles[k] = nil
	-- end
end

function bee.invokeUi(funcName)
	P:invoke(funcName)
end

