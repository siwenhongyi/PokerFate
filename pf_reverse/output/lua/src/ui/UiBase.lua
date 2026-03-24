-- 界面
local P = class("UiBase", Object)
UiBase = P

function P:ctor()
	P.super.ctor(self)
	self.uiName = self.__cname
	self._is_showing = false --界面是否正在开启
	self._is_hiding = false  --界面是否正在关闭
	self._is_show = false    --界面是否开启
	self._autoAdapt = false
	self._needShowAnim = true

	self._watiStart = true 	-- 等待 onStart 完成
	self._isMute = nil 	-- 是否静音
end

local offsetMax, offsetMin = nil, nil
function P:__setAdapt(top, bottom, left, right)
	-- if top ~= 0 or bottom ~= 0 or left ~= 0 or right ~= 0 then
		offsetMax = bee.v2(left, top)
		offsetMin = bee.v2(right, bottom)
	-- end
end

function P:onAdapt()
	if self._autoAdapt and offsetMax and offsetMin and self.node.transform.offsetMax then
		self.node.transform.offsetMax = offsetMax
		self.node.transform.offsetMin = offsetMin
	end
end

function P:setParams(params)
	self._params = params
	if self._params and self._params.needShowAnim ~= nil then
		self._needShowAnim = self._params.needShowAnim
	end
end

function P:onAwake() end

function P:onStart() end

function P:onDestroy()
	self:setShow(false)
	P.super.onDestroy(self)
end

function P:isShowing()
	return self._is_showing
end

function P:setShowing(bShowing)
	self._is_showing = bShowing
end

function P:isHiding()
	return self._is_hiding
end

function P:setHiding(bHiding)
	self._is_hiding = bHiding
end

function P:isShow()
	return self._is_show
end

function P:setShow(bShow)
	self._is_show = bShow
end

function P:_doShow()
	if bee.isNull(self.node) then
		return
	end
	if tpl_ui_config and tpl_ui_config[self.uiName] then
		local sound = tpl_ui_config[self.uiName].sound
		if sound then
			sound = sound == 1 and "open" or "popup"
		end
		if Game and sound then
			Game:playSound(sound)
		end
	end
	if self:isShowing() then
		return
	end
	self:setShowing(true)
	self:preShow()
	self:onShow()
	self:checkShowAnim()
end

function P:playAnimator(name, node)
	local AnimRoot = node or self:find("AnimRoot")
	if AnimRoot then
		local animator = AnimRoot:GetComponent("Animator")
		if not bee.isNull(animator) then
			animator:Play(name, -1, 0)
		end
	end
end

function P:checkShowAnim()
	if bee.isNull(self.node) then
		return
	end
	local animator = self.node:GetComponent("Animator")
	if bee.isNull(animator) then
		local popDialog = self:find("AnimRoot") or self:find("PopDialog")
		if not bee.isNull(popDialog) then
			animator = popDialog:GetComponent("Animator")
		end
	end

	if not bee.isNull(animator) and self._needShowAnim ~= false then
		local dialogNode = animator.transform:Find("Dialog")
		if not bee.isNull(dialogNode) then
			local cg = dialogNode.gameObject:GetComponent("CanvasGroup")
			if not cg or bee.isNull(cg) then
				printError(self.node.name .. " Dialog节点 缺少 CanvasGroup组件...")
			end
		end
		self.animator = animator
		local length = self:getAnimatorLength(animator, self._openAnim or "UI_common_notice_into")
		self:once(length, function()
			if not bee.isNull(self.node) then
				self:afterShow()
				self:setShowing(false)
				self:setShow(true)
			end
		end)
	else
		if not bee.isNull(animator) then
			animator.enabled = false
		end
		self:afterShow()
		self:setShowing(false)
		self:setShow(true)
	end
end

--Destroy时调用
function P:_doHide()
	self:onHide()
	self:afterHide()
end

function P:preShow()
end

function P:onShow()
	-- ui被显示，子类实现
end

function P:afterShow()
	-- ui完成显示动画，子类实现
end

function P:preHide()
	if self._params and self._params.preHideCb then
		self._params.preHideCb()
	end
end

function P:onHide()
	-- ui被隐藏，子类实现
end


function P:afterHide()
	-- ui完成隐藏，子类实现
	if self._params and self._params.hideCb then
		self._params.hideCb()
		self._params.hideCb = nil
	end
end

function P:hideUI(cb, noSound)
	if Game and not noSound and not self._isMute then
		Game:playSound("ui_close")
	end
	if not self._is_show then
		return
	end
	if self:isHiding() then
		if cb then cb() end
		return
	end
	self:setHiding(true)
	self:checkHideAnim(cb)
end

function P:hideUIForce()
	self:preHide()
	UiManager:hideUIByCls(self)
end

function P:checkHideAnim(cb)
	if not bee.isNull(self.animator) and self._closeAnim ~= "" then
		if AnimationMgr then
			AnimationMgr:playAnimator(self.animator, self._closeAnim or "UI_common_notice_back")
		else
			if cb then cb() end
			self:setHiding(false)
			self:setShow(false)
			UiManager:hideUIByCls(self)
		end
	end
	self:preHide()
	
	local dt = 0
	-- ui 准备被隐藏，返回所需要的动画时间, 子类有其他动画时可复写
	if not bee.isNull(self.animator) and self._closeAnim ~= "" then
		dt = self:getAnimatorLength(self.animator, self._closeAnim or "UI_common_notice_back")
	end
	if dt and dt > 0 then
		self:once(dt, function() 
			self:setHiding(false)
			self:setShow(false)
			if cb then cb() end
		end)
		if not bee.isNull(self.node) then
			UiManager:hideUIByCls(self, dt + 0.1)
		end
	else
		self:setHiding(false)
		self:setShow(false)
		if cb then cb() end
		if not bee.isNull(self.node) then
			UiManager:hideUIByCls(self)
		end
	end
end

function P:getAnimatorLength(animator, stateName)
	return CS.AnimatorManager.Instance:GetAnimationTimes(animator, stateName) or 0
end

-- 获取当前界面的层级 + offset
function P:getRootSortingOrder(offset)
	if bee.isNull(self.node) then
		return UiManager.sortingIndex * 20 + offset
	end
	local canvas = self.node:GetComponent("Canvas")
	if not bee.isNull(canvas) then
		return canvas.sortingOrder + offset
	end
	return UiManager.sortingIndex * 20 + offset
end

