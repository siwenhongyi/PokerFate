local P = class("SpiritCatStyleTip", UiDialog)

function P:onAwake()
	local Panel = self:find("AnimRoot/Center/Panel")

	self.RichTextTip = self:find("RichTextTip", Panel)
	self.TextTip = self:find("TextTip", Panel)
	self.ConfirmButton = self:find("ConfirmButton", Panel)
	self.CancelButton = self:find("CancelButton", Panel)
	self.CloseButton = self:find("CloseButton", Panel)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.CancelButton, function()
		self:hideUI()
	end)
	bee.addClick(self.ConfirmButton, function()
		self._params.onSure()
		self:hideUI()
	end)
end

function P:onStart()
	if self._params.richText then
		self.RichTextTip:SetActive(true)
		bee.setText(self.RichTextTip, self._params.richText)
	elseif self._params.text then
		self.TextTip:SetActive(true)
		bee.setText(self.TextTip, self._params.text)
	end
end

return P