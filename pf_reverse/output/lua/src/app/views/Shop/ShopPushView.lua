local P = class("ShopPushView", UiFullView)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)

	self.ContentList = self:find("ContentList/Content", Center)
	self.PanelLeft = self:find("PanelLeft", self.ContentList)
	self.PanelCenter = self:find("PanelCenter", self.ContentList)
	self.PanelRight = self:find("PanelRight", self.ContentList)
	self.TabBottom = self:find("TabBottom", Center)
	self.Switch = self:find("Switch", self.TabBottom)
	self.Switch:SetActive(false)
	self.CloseButton = self:find("CloseButton", Center)

	self.PageLastButton = self:find("Left/PageLastButton", AnimRoot)
	self.PageNextButton = self:find("Right/PageNextButton", AnimRoot)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)

	self.PanelLeft.transform.sizeDelta = bee.v2(SCREEN_WIDTH, SCREEN_HEIGHT)
	self.PanelCenter.transform.sizeDelta = bee.v2(SCREEN_WIDTH, SCREEN_HEIGHT)
	self.PanelRight.transform.sizeDelta = bee.v2(SCREEN_WIDTH, SCREEN_HEIGHT)

	bee.addClick(self.PageLastButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickLast()
	end)
	bee.addClick(self.PageNextButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickNext()
	end)
end

function P:onStart()
	if self._params and self._params.isAuto then
		ShopModel:recordAutoShowShopPush()
	end

	self.showList = ShopModel:getShopPushList()
	if not self.showList or not next(self.showList) then
		return
	end

	self._viewList = {}
	self.switchItemList = {}
	for i, v in ipairs(self.showList) do
		local subView = bee.createObj(v.view)
		local subViewCls = ObjectPool:getCls(subView)
		self._viewList[i] = {node = subView, cls = subViewCls}
		subView:SetActive(false)

		local Ani_root = self:find("Ani_root", subView)
		if Ani_root then
			Ani_root.transform.localPosition = bee.v3(0, 0, 0)
		end

		local switch = CU.GameObject.Instantiate(self.Switch)
		switch.transform:SetParent(self.TabBottom.transform)
		switch.transform.localPosition = bee.v3(0, 0, 0)
		switch.transform.localScale = bee.v3(1, 1, 1)
		switch:SetActive(true)
		self.switchItemList[i] = switch
	end

	self._maxIndex = #self.showList
	self._curIndex = math.random(1, self._maxIndex)

	if self._maxIndex == 1 then
		self.PageLastButton:SetActive(false)
		self.PageNextButton:SetActive(false)
		self.TabBottom:SetActive(false)
	end

	self:initViewPos()
	self:refreshSwitch()
end

function P:initViewPos()
	local centerNode = self._viewList[self._curIndex].node
	centerNode.transform:SetParent(self.PanelCenter.transform)
	centerNode.transform.localPosition = bee.v3(SCREEN_WIDTH / 2, 0, 0)
	centerNode.transform.localScale = bee.v3(1, 1, 1)
	centerNode:SetActive(true)
end

function P:refreshSwitch()
	for i, v in ipairs(self.switchItemList) do
		self:find("Off", v):SetActive(i ~= self._curIndex)
		self:find("On", v):SetActive(i == self._curIndex)
	end
end

function P:onClickLast()
	if self._isMoving then
		return
	end
	self._isMoving = true

	local nextIndex = self._curIndex - 1
	if nextIndex < 1 then
		nextIndex = self._maxIndex
	end

	local nextNode = self._viewList[nextIndex].node
	nextNode.transform:SetParent(self.PanelLeft.transform)
	nextNode.transform.localPosition = bee.v3(SCREEN_WIDTH / 2, 0, 0)
	nextNode.transform.localScale = bee.v3(1, 1, 1)
	nextNode:SetActive(true)

	bee.tween(self.ContentList)
	:to(0.1, {x = SCREEN_WIDTH})
	:onComplete(function()
		nextNode.transform:SetParent(self.PanelCenter.transform)
		nextNode.transform.localPosition = bee.v3(SCREEN_WIDTH / 2, 0, 0)
		self.ContentList.transform.localPosition = bee.v3(0, 0, 0)

		local curNode = self._viewList[self._curIndex].node
		curNode:SetActive(false)

		self._curIndex = nextIndex
		self._isMoving = false

		self:refreshSwitch()
	end)
end

function P:onClickNext()
	if self._isMoving then
		return
	end
	self._isMoving = true

	local nextIndex = self._curIndex + 1
	if nextIndex > self._maxIndex then
		nextIndex = 1
	end

	local nextNode = self._viewList[nextIndex].node
	nextNode.transform:SetParent(self.PanelRight.transform)
	nextNode.transform.localPosition = bee.v3(SCREEN_WIDTH / 2, 0, 0)
	nextNode.transform.localScale = bee.v3(1, 1, 1)
	nextNode:SetActive(true)

	bee.tween(self.ContentList)
	:to(0.1, {x = -SCREEN_WIDTH})
	:onComplete(function()
		nextNode.transform:SetParent(self.PanelCenter.transform)
		nextNode.transform.localPosition = bee.v3(SCREEN_WIDTH / 2, 0, 0)
		self.ContentList.transform.localPosition = bee.v3(0, 0, 0)

		local curNode = self._viewList[self._curIndex].node
		curNode:SetActive(false)

		self._curIndex = nextIndex
		self._isMoving = false

		self:refreshSwitch()
	end)
end

function P:onEndDrag(e)
	if self._maxIndex == 1 then
		return
	end
	if e.delta.x > 0 then
		self:onClickLast()
	else
		self:onClickNext()
	end
end

function P:evt_updateShopLimit()
	for k, v in pairs(self._viewList) do
		v.cls:refreshUI()
	end
end

