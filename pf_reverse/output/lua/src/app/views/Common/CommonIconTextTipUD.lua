local P = class("CommonIconTextTipUD", UiBase)

function P:onAwake()
	P.super.onAwake(self)
	self.inPop = true

	self.Mask = self:find("Mask")
    self.ItemTips = self:find("ItemTips")

    self.Icon = self:find("Icon", self.ItemTips)
    self.TextTip = self:find("TextTip", self.ItemTips)
    self.ImageBg = self:find("ImageBg", self.ItemTips)
    self.UpArrow = self:find("UpArrow", self.ImageBg)
    self.DownArrow = self:find("DownArrow", self.ImageBg)

	bee.addClick(self.Mask, function ()
		self:hideUI()
	end)
end

--[[
	text: 提示文本, target: 提示目标位置
]]
function P:onShow()
	bee.setIconInAtlas(self.Icon, self._params.icon, true)
    bee.setText(self.TextTip, self._params.text or "")
    
    CS.Utils.ForceRebuildLayoutImmediate(self.ItemTips)
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
	local endPosX, endPosY = self.assetItemPosition.x, self.assetItemPosition.y

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

    if target.transform.position.y <= 0 then
        endPosY = endPosY + offset + 24
        self.UpArrow:SetActive(false)
        self.DownArrow:SetActive(true)
        self.DownArrow.transform.localPosition = bee.v3(xChange, self.DownArrow.transform.localPosition.y)
    else
        endPosY = endPosY - offset - 24
        self.UpArrow:SetActive(true)
        self.DownArrow:SetActive(false)
        self.UpArrow.transform.localPosition = bee.v3(xChange, self.UpArrow.transform.localPosition.y)
    end

	self.ItemTips.transform.localPosition = bee.v3(endPosX, endPosY)
end

return P