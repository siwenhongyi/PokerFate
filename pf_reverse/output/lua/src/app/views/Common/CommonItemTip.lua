local P = class("CommonItemTip", UiBase)

function P:onAwake()
	P.super.onAwake(self)
	self.inPop = true

	self.Mask = self:find("Mask")
    self.ItemTips = self:find("ItemTips")

    self.PropItemObj = self:find("PropItem", self.ItemTips)
    self.TextName = self:find("TextName", self.ItemTips)
    self.TextDec = self:find("DescScrollView/Viewport/Content/TextDec", self.ItemTips)
    self.ViewIcon = self:find("ViewIcon", self.ItemTips)
    self.TopArrow = self:find("TopArrow", self.ItemTips)
    self.BottomArrow = self:find("BottomArrow", self.ItemTips)

	self.Ani_root = self:find("Ani_root")

	bee.addClick(self.Mask, function ()
		self:hideUI()
	end)
end

--[[
	data: 道具数据, target: 提示目标位置, format: 文本内容提示格式化列表
]]
function P:onShow()
    self._data = self._params.data

    local id = self._data.item_id or self._data.id
    PropItem:create(self.PropItemObj, {id = id, count = 1, icon = self._params.icon}):bindPreview()

    local d = tpl_props[self._data.item_id or self._data.id]
    bee.setText(self.TextName, _T(d.name))
	if self._params.format then
    	bee.setText(self.TextDec, _F(d.des, unpack(self._params.format)))
	elseif self._data.format then
    	bee.setText(self.TextDec, _F(d.des, unpack(self._data.format)))
	else
		bee.setText(self.TextDec, ItemModel:getItemDesText(d.id))
	end
    if d.preview == 1 then
    	self.ViewIcon:SetActive(true)
    	if d.type == GPropKind.MusicLobby or d.type == GPropKind.MusicTable then
    		bee.setIcon(self.ViewIcon, "backpack_icon_play", "Backpack")
    	else
    		bee.setIcon(self.ViewIcon, "backpack_icon_view", "Backpack")
    	end
    else
    	self.ViewIcon:SetActive(false)
    end

    self:setContentPos()
end

function P:setContentPos()
    local target = self._params.target
	self.assetItemPosition = CS.Utils.UtilsWorldToScreenPoint(self.node, target)
	self.assetItemPivot = target:GetComponent("RectTransform").pivot
	self.assetItemRect = target:GetComponent("RectTransform").rect

	local selfWidth = self.ItemTips:GetComponent("RectTransform").rect.width
	local selfHeight = self.ItemTips:GetComponent("RectTransform").rect.height
	
	local w, h = self.node.transform.rect.width + Config.UI_OFFSET_LEFT * 2, self.node.transform.rect.height
	local offset = selfHeight / 2  + self.assetItemRect.height / 2
	local endPosX, endPosY = self.assetItemPosition.x, self.assetItemPosition.y + offset

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
		endPosY = self.assetItemPosition.y - offset - 30
		self.TopArrow:SetActive(true)
		self.BottomArrow:SetActive(false)
		self.TopArrow.transform.localPosition = bee.v3(xChange, self.TopArrow.transform.localPosition.y)
	else
		self.TopArrow:SetActive(false)
		self.BottomArrow:SetActive(true)
		self.BottomArrow.transform.localPosition = bee.v3(xChange, self.BottomArrow.transform.localPosition.y)
	end

	self.ItemTips.transform.localPosition = bee.v3(endPosX, endPosY)

	self.Ani_root.transform.position = self.TopArrow.activeSelf and self.TopArrow.transform.position or self.BottomArrow.transform.position
	self.ItemTips.transform:SetParent(self.Ani_root.transform, true)
end

return P