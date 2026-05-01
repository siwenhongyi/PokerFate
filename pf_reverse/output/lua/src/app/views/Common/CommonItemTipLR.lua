local P = class("CommonItemTipLR", UiBase)

function P:onAwake()
	P.super.onAwake(self)

	self.inPop = true

	self.Mask = self:find("Mask")
    self.ItemTips = self:find("ItemTips")

    self.PropItemObj = self:find("PropItem", self.ItemTips)
    self.TextName = self:find("TextName", self.ItemTips)
    self.TextDec = self:find("DescScrollView/Viewport/Content/TextDec", self.ItemTips)
    self.ViewIcon = self:find("ViewIcon", self.ItemTips)
    self.LeftArrow = self:find("LeftArrow", self.ItemTips)
    self.RightArrow = self:find("RightArrow", self.ItemTips)

	bee.addClick(self.Mask, function()
		self:hideUI()
	end)
end

function P:onShow()
    self._data = self._params.data

    local id = self._data.item_id or self._data.id
    PropItem:create(self.PropItemObj, {id = id, count = 1}):bindPreview()

    local d = tpl_props[self._data.item_id or self._data.id]
    bee.setText(self.TextName, _T(d.name))
	if self._params.format then
    	bee.setText(self.TextDec, _F(d.des, unpack(self._params.format)))
	else
		bee.setText(self.TextDec, _T(d.des))
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
	
	local w, h = self.node.transform.rect.width, self.node.transform.rect.height + Config.UI_OFFSET_LEFT * 2
	local offset = selfWidth / 2  + self.assetItemRect.width / 2
	local endPosX, endPosY = self.assetItemPosition.x, self.assetItemPosition.y

    if target.transform.position.x <= 0 then
        endPosX = endPosX + offset
        self.LeftArrow:SetActive(true)
        self.RightArrow:SetActive(false)
    else
        endPosX = endPosX - offset
        self.LeftArrow:SetActive(false)
        self.RightArrow:SetActive(true)
    end

	self.ItemTips.transform.localPosition = bee.v3(endPosX, endPosY)
end

return P