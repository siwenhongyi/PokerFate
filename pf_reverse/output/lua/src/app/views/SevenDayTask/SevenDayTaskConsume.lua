local P = class("SevenDayTaskConsume", UiDialog)

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")

	local Center = self:find("Center", self.AnimRoot)
	self.ConfirmButton = self:find("ConfirmButton", Center)
	self.CancelButton = self:find("CancelButton", Center)
	self.CloseButton = self:find("CloseButton", Center)
	self.ClaimButton = self:find("ClaimButton", Center)
	self.PropItemObj = self:find("PropItem", Center)
	self.NumText = self:find("PropItem/NumText", Center)

	bee.addClick(self.ConfirmButton, function()
		if self._params.confirmCb then
			self._params.confirmCb()
		end
		self:hideUI()
	end)
	bee.addClick(self.CancelButton, function()
		self:hideUI()
	end)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.ClaimButton, function()
		ItemModel:jumpView(tpl_constdata.Signature_Card_Path)
	end)
end

function P:evt_ItemChangeRSP()
	self:refreshCount()
end

function P:onStart()
	PropItem:create(self.PropItemObj, {item_id = GPropId.ReSign, num = 0}):bindTips()
	self:refreshCount()
end

function P:refreshCount()
	local ownCount = ItemModel:getItemNumById(GPropId.ReSign)
	if ownCount >= 1 then
		self.CancelButton:SetActive(true)
		self.ConfirmButton:SetActive(true)
		self.ClaimButton:SetActive(false)
		bee.setText(self.NumText, ownCount .. "/" .. 1)
	else
		self.ConfirmButton:SetActive(false)
		self.CancelButton:SetActive(false)
		self.ClaimButton:SetActive(true)
		bee.setText(self.NumText, _F("LAB_CHAR_068", ownCount, 1))
	end
end

