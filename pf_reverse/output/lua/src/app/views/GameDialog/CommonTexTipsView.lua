---@class CommonTexTipsView
local P = class("CommonTexTipsView", UiBase)

local DescriptionForward =
{
	Up = 1,
	Down = 2,
}

function P:ctor(params)
	P.super.ctor(self, params)
end

function P:onAwake()
	P.super.onAwake(self)
	self.inPop = true
	self.CloseMask = self:find("CloseMask")

	self.UpDescriptionCont = self:find("UpDescriptionCont")
	self.Root = self:find("Root", self.UpDescriptionCont)
	self.ContBg = self:find("ContBg", self.Root)
	self.DescriptionText = self:find("DescriptionText", self.ContBg)

	self.BottomArrow = self:find("BottomArrow", self.Root)
	self.TopArrow = self:find("TopArrow", self.Root)
	self.UpDescriptionContCanvasGroup = self.UpDescriptionCont:GetComponent("CanvasGroup")
	self.UpDescriptionContCanvasGroup.alpha = 0

	bee.AddClick(self.CloseMask, function ()
		self:hideUI()
	end)
end

function P:setParams(params)
	P.super.setParams(self, params)
	self.showContent = params.content
	self.assetItem = params.target
	self.forward = params.forward
	self.pos = params.pos

	self:onDescriptionShow()
end

function P:onDescriptionShow()
	bee.setText(self.DescriptionText, self.showContent)
	bee.setText(self.DownDescriptionText, self.showContent)

	self:once(0.1, function ()
		if bee.isNull(self.assetItem) then
			self.TopArrow:SetActive(false)
			self.BottomArrow:SetActive(false)
			self.UpDescriptionCont.transform.localPosition = self.pos or bee.v3(0, 0)
		else
			self:setContentPos()
		end
		self.UpDescriptionContCanvasGroup.alpha = 1
	end)
end

function P:setContentPos()
	self.assetItemPosition = CS.Utils.UtilsWorldToScreenPoint(self.node, self.assetItem)
	self.assetItemPivot = self.assetItem:GetComponent("RectTransform").pivot
	self.assetItemRect = self.assetItem:GetComponent("RectTransform").rect

	local selfWidth = self.ContBg:GetComponent("RectTransform").rect.width
	local selfHeight = self.ContBg:GetComponent("RectTransform").rect.height
	
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
		if xChange ~= 0 then
			self.TopArrow.transform.anchoredPosition = bee.v2(xChange, self.TopArrow.transform.anchoredPosition.y)
		end
	else
		self.TopArrow:SetActive(false)
		self.BottomArrow:SetActive(true)
		if xChange ~= 0 then
			self.BottomArrow.transform.anchoredPosition = bee.v2(xChange, self.BottomArrow.transform.anchoredPosition.y)
		end
	end

	self.UpDescriptionCont.transform.localPosition = bee.v3(endPosX, endPosY)
end

return P