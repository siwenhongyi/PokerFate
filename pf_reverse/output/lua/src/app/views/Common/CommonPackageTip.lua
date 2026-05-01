local P = class("CommonPackageTip", UiBase)

function P:onAwake()
	P.super.onAwake(self)

	self.ItemList = self:find("ItemList")
	self.ItemRow = self:find("ItemRow")
	self.Item1 = self:find("Item1")
	self.ItemRow:SetActive(false)
	self.Item1:SetActive(false)
	bee.setAlpha(self.ItemList, 0)

	self.TopArrow = self:find("TopArrow", self.ItemList)
	self.BottomArrow = self:find("BottomArrow", self.ItemList)

	self.ClickMask = self:find("ClickMask")
	bee.addClick(self.ClickMask, function()
		self:hideUI()
	end)
end

function P:onStart()
	
end

function P:setRewardCont()
	local items = self._params.items or {}
	local rowCount = math.ceil(#items / 4)
	for i = 1, rowCount do
		local rowObj = CU.GameObject.Instantiate(self.ItemRow)
		rowObj.transform:SetParent(self.ItemList.transform)
		rowObj.transform.localPosition = bee.v3(0, 0, 0)
		rowObj.transform.localScale = bee.v3(1, 1, 1)
		rowObj:SetActive(true)

		local c = 4
		if rowCount <= 1 then
			c = #items
		end
		for j = 1, c do
			local itemObj = CU.GameObject.Instantiate(self.Item1)
			itemObj.transform:SetParent(rowObj.transform)
			itemObj.transform.localPosition = bee.v3(0, 0, 0)
			itemObj.transform.localScale = bee.v3(1, 1, 1)
			itemObj:SetActive(true)
				
			local d = items[(i - 1) * 4 + j]
			if d then
				PropItem:create(self:find("PropItem", itemObj), d)
			else
				self:find("PropItem", itemObj):SetActive(false)
			end
		end
	end
end

function P:onShow()
	self:setRewardCont()
	self:once(0.01, function()
		self:setContentPos()
		bee.setAlpha(self.ItemList, 1)
	end)
end

function P:setContentPos()
    local target = self._params.target
	self.assetItemPosition = CS.Utils.UtilsWorldToScreenPoint(self.node, target)
	self.assetItemPivot = target:GetComponent("RectTransform").pivot
	self.assetItemRect = target:GetComponent("RectTransform").rect

	local selfWidth = self.ItemList:GetComponent("RectTransform").rect.width
	local selfHeight = self.ItemList:GetComponent("RectTransform").rect.height
	
	local w, h = self.node.transform.rect.width, self.node.transform.rect.height + Config.UI_OFFSET_LEFT * 2
	local offset = selfHeight / 2  + self.assetItemRect.height
	local endPosX, endPosY = self.assetItemPosition.x, self.assetItemPosition.y - offset

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
	self.ItemList.transform.localPosition = bee.v3(endPosX, endPosY)

	if self.ItemList.transform.position.y < target.transform.position.y then
		endPosY = self.assetItemPosition.y - offset - 30
		self.TopArrow:SetActive(true)
		self.BottomArrow:SetActive(false)
		self.TopArrow.transform.localPosition = bee.v3(xChange, self.TopArrow.transform.localPosition.y)
	else
		self.TopArrow:SetActive(false)
		self.BottomArrow:SetActive(true)
		self.BottomArrow.transform.localPosition = bee.v3(xChange, self.BottomArrow.transform.localPosition.y)
	end

end


--引导
function P:evt_guide_turn_challenge()
	self:hideUI()
end

return P