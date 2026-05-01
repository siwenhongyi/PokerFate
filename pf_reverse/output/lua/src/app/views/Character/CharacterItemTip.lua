local P = class("CharacterItemTip", UiBase)

function P:onAwake()
	P.super.onAwake(self)
	self.inPop = true

	self.Mask = self:find("Mask")
    self.ItemTips = self:find("ItemTips")

    self.Item = self:find("Item", self.ItemTips)
    self.Item:SetActive(false)

    self.TopArrow = self:find("TopArrow", self.ItemTips)
    self.BottomArrow = self:find("BottomArrow", self.ItemTips)

	self.Ani_root = self:find("Ani_root")

	bee.addClick(self.Mask, function ()
		self:hideUI()
	end)
end

--[[
	items: 道具id列表, target: 提示目标位置
]]
function P:onShow()
    self._items = self._params.items

    for k, v in ipairs(self._items) do
        local item = CU.GameObject.Instantiate(self.Item, self.ItemTips.transform, false)
        item:SetActive(true)
        local d = tpl_props[v]
        bee.setIcon(self:find("Icon", item), d.icon)
        bee.setText(self:find("TextName", item), _T(d.name))
        if k == #self._items then
            self:find("Line", item):SetActive(false)
        end
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
        endPosY = endPosY + 35
		self.TopArrow:SetActive(false)
		self.BottomArrow:SetActive(true)
		self.BottomArrow.transform.localPosition = bee.v3(xChange, self.BottomArrow.transform.localPosition.y)
	end

	self.ItemTips.transform.localPosition = bee.v3(endPosX, endPosY)

	self.Ani_root.transform.position = self.TopArrow.activeSelf and self.TopArrow.transform.position or self.BottomArrow.transform.position
	self.ItemTips.transform:SetParent(self.Ani_root.transform, true)
end

return P