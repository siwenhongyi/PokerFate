local P = class("CommonTextTipRL", UiBase)

function P:onAwake()
	P.super.onAwake(self)
	self.inPop = true

	self.Mask = self:find("Mask")
    self.ItemTips = self:find("ItemTips")

    self.TextTip = self:find("TextTip", self.ItemTips)
    self.LeftArrow = self:find("LeftArrow", self.ItemTips)
    self.RightArrow = self:find("RightArrow", self.ItemTips)

	bee.addClick(self.Mask, function ()
		self:hideUI()
	end)
end

--[[
	text: 提示文本, target: 提示目标位置
]]
function P:onShow()
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
	
	local w, h = self.node.transform.rect.width + Config.UI_OFFSET_LEFT * 2, self.node.transform.rect.height
	local offset = selfWidth / 2  + self.assetItemRect.width / 2
	local endPosX, endPosY = self.assetItemPosition.x, self.assetItemPosition.y

	local tipH = self.ItemTips.transform.rect.height
    local offsetY = 0
    if endPosY + tipH / 2 > h / 2 then
        offsetY = endPosY + tipH / 2 - h / 2
    elseif endPosY - tipH / 2 < - h / 2 then
        offsetY = endPosY - tipH / 2 + h / 2
    end
    endPosY = endPosY - offsetY

    if target.transform.position.x <= 0 then
        endPosX = endPosX + offset
        self.LeftArrow:SetActive(true)
        self.RightArrow:SetActive(false)
        self.LeftArrow.transform.localPosition = bee.v3(self.LeftArrow.transform.localPosition.x, offsetY)
    else
        endPosX = endPosX - offset
        self.LeftArrow:SetActive(false)
        self.RightArrow:SetActive(true)
        self.RightArrow.transform.localPosition = bee.v3(self.RightArrow.transform.localPosition.x, offsetY)
    end

	self.ItemTips.transform.localPosition = bee.v3(endPosX, endPosY)
end

return P