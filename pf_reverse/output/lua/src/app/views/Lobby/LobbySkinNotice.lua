local P = class("LobbySkinNotice", UiDialog)

function P:onAwake()
	local Notice = self:find("AnimRoot/Center/Notice")

	self.CountText = self:find("CountText", Notice)
	self.ConfirmButton = self:find("ConfirmButton", Notice)
	self.CancelButton = self:find("CancelButton", Notice)
	self.CloseButton = self:find("CloseButton", Notice)
	self.TextTip = self:find("TextTip", Notice)

	bee.addClick(self.ConfirmButton, function()
		self:onClickJump()
	end)
	bee.addClick(self.CancelButton, function()
		self:hideUI()
	end)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
end

function P:onStart()
	bee.setText(self.TextTip, _F("LAB_CUSTOM_1", self._params.count))
	bee.setText(self.CountText, _F("LAB_CUSTOM_2", self._params.curCount, self._params.count))
end

function P:onClickJump()
	ItemModel:jumpView(5001)
	self:hideUI()
	
end

