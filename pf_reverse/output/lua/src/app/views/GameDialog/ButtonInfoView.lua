---@class ButtonInfoView
local P = class("ButtonInfoView", UiBase)
local UIPassEvent = CS.UIPassEvent

function P:ctor(params)
	P.super.ctor(self, params)
	-- self.inPop = true
	self.btnItemList = {}
end

function P:onAwake()
	self.main = self:find("Main")
	self.mainTrans = self:find("Main"):GetComponent("RectTransform")
	self.topArrow = self:find("Main/TopArrow")
	self.bottomArrow = self:find("Main/BottomArrow")
	self.box = self:find("Main/Box")
	self.item = self:find("1", self.box)
	self.item.gameObject:SetActive(false)

	self.mainCanvasGroup = self.main:GetComponent("CanvasGroup")
	self.mainCanvasGroup.alpha = 0

	self.closeBtn = self:find("BtClose")
end

function P:onShow()
	self.btnList = self._params.btnList
	self.target = self._params.target
	self.noRaycast = self._params.noRaycast or false

	if self.noRaycast then
		local passevent = UIPassEvent.Get(self.closeBtn)
		if not bee.isNull(passevent) then
			passevent.onBeginDrag:RemoveAllListeners()
			passevent.onBeginDrag:AddListener(function(go, eventData)
				self.main:SetActive(false)
			end)
			passevent.onEndDrag:RemoveAllListeners()
			passevent.onEndDrag:AddListener(function(go, eventData)
				self:hideUI()
			end)
			passevent.onClick:RemoveAllListeners()
			passevent.onClick:AddListener(function(go, eventData)
				self:hideUI()
			end)
		end
	else
		bee.removeAllClick(self.closeBtn)
		bee.addClick(self.closeBtn, function() 
			self:hideUI()
		end)
	end

	self:setBtns()

	bee.once(0.1, function ()
		self:setPos()
		self.mainCanvasGroup.alpha = 1
	end, self.node)
end

function P:setPos()
	self.targetPosition = CS.Utils.UtilsWorldToScreenPoint(self.box, self.target)
	local targetHeight = self.target:GetComponent("RectTransform").rect.height
	local selfWidth = self.mainTrans.rect.width
	local selfHeight = self.mainTrans.rect.height

	local w, h = self.node.transform.rect.width, self.node.transform.rect.height + Config.UI_OFFSET_LEFT * 2
	local offset = selfHeight / 2  + targetHeight / 2
	local endPosX, endPosY = self.targetPosition.x, self.targetPosition.y + offset

	local xChange = 0
	if endPosX + selfWidth / 2 > w / 2 then
		local temp = endPosX
		endPosX = w / 2 - selfWidth/2
		xChange = temp - endPosX
	elseif endPosX - selfWidth / 2 < - w / 2 then
		local temp = endPosX
		endPosX = -w / 2 + selfWidth / 2
		xChange = temp - endPosX
	end
	if endPosY + selfHeight / 2 > h / 2 then
		endPosY = self.targetPosition.y - offset
		self.topArrow:SetActive(true)
		self.bottomArrow:SetActive(false)
		if xChange ~= 0 then
			self.topArrow.transform.anchoredPosition = bee.v2(xChange, self.topArrow.transform.anchoredPosition.y)
		end
	else
		self.topArrow:SetActive(false)
		self.bottomArrow:SetActive(true)
		if xChange ~= 0 then
			self.bottomArrow.transform.anchoredPosition = bee.v2(xChange, self.bottomArrow.transform.anchoredPosition.y)
		end
	end

	self.mainTrans.localPosition = bee.v3(endPosX, endPosY)
end

function P:setBtns()
	local btnCount = table.nums(self.btnList)
	local itemCount = table.nums(self.btnItemList)
	local needCount = math.max(btnCount - itemCount, 0)
	if needCount > 0 then
		for i = 1, needCount do
			local btnItem = CU.GameObject.Instantiate(self.item)
			local btnTrans = btnItem.transform
			btnTrans:SetParent(self.box.transform, false)
			btnTrans.localScale = bee.v3(1, 1, 1)
			btnItem.gameObject:SetActive(true)
			table.insert(self.btnItemList, btnItem)
		end
	end

	for i = 1, btnCount do
		local btnItem = self.btnItemList[i]
		local btnData = self.btnList[i]
		bee.RemoveAllClick(btnItem)
		bee.addClick(btnItem, function() 
			local cb = btnData[3]
			if cb then cb() end
		end)

		bee.setIcon(btnItem.transform, btnData[1] or "ButtonNormalGreen_1", "CommonUI")
		bee.setText(self:find("Text" ,btnItem), btnData[2])
		btnItem:SetActive(true)
	end

	for i = btnCount + 1, itemCount do
		local btnItem = self.btnItemList[i]
		btnItem:SetActive(false)
	end
end

function P:hide()
	self.node:SetActive(false)
	self.mainCanvasGroup.alpha = 0
end

function P:onDestroy()
    P.super.onDestroy(self)
end

