local P = class("CommonTextTipUD", UiBase)

function P:onAwake()
	P.super.onAwake(self)
	self.inPop = true

	self.Mask = self:find("Mask")
    self.ItemTips = self:find("ItemTips")

    self.TextTip = self:find("TextTip", self.ItemTips)
    self.ImageBg = self:find("ImageBg", self.ItemTips)
    self.UpArrow = self:find("UpArrow", self.ImageBg)
    self.DownArrow = self:find("DownArrow", self.ImageBg)

	bee.addClick(self.Mask, function ()
		self:onBtClose()
	end)
end

--[[
	text: 提示文本, target: 提示目标位置
]]
function P:onShow()
	self.closeCb = self._params.closeCb
	self.adaptive = self._params.adaptive or false
    bee.setText(self.TextTip, self._params.text or "")
    
    CS.Utils.ForceRebuildLayoutImmediate(self.ItemTips)
    self:setContentPos()
	self:setAdaptive()
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

function P:setAdaptive()
	if not self.adaptive then
		return
	end
	
	local textWidth = self.TextTip:GetComponent("Text").preferredWidth
	if textWidth > self.TextTip.transform.sizeDelta.x then
		return
	end

	self.TextTip.transform.sizeDelta = bee.v2(textWidth, 0)
	self.ItemTips.transform.sizeDelta = bee.v2(textWidth + 60 * 2, self.ItemTips.transform.sizeDelta.y)
end

function P:evt_hideUiWhenAction(isVisible)
    if not isVisible then
    	self:hideUIForce()
    end
end

function P:onBtClose()
	self:hideUI()
	if self.closeCb then
		self.closeCb()
	end
end

return P