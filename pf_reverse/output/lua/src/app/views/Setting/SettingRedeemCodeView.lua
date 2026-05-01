local P = class("SettingRedeemCodeView", UiDialog)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)

	self.InputFieldCode = self:find("InputFieldCode", Center)
	self.TipsText = self:find("TipsText", Center)
	self.ConfirmButton = self:find("ConfirmButton", Center)
	self.CancelButton = self:find("CancelButton", Center)
	self.CloseButton = self:find("CloseButton", Center)
	bee.setText(self.TipsText, "")

	bee.addClick(self.CancelButton, function()
		self:hideUI()
	end)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.ConfirmButton, function()
		self:onClickCommit()
	end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)
end

function P:onStart()
end

function P:onClickCommit()
	local inputCode = bee.getText(self.InputFieldCode, "InputField")
	if inputCode == "" then
		bee.setText(self.TipsText, _T("LAB_SETTINGS_101"))
		return
	end
	bee.setText(self.TipsText, "")

	local limitCb = function()
		bee.setText(self.TipsText, _T("LAB_SETTINGS_103"))
	end
	local errCb = function(errCode)
		if errCode == -701 then
			bee.setText(self.TipsText, _T("LAB_SETTINGS_104"))
		elseif errCode == -703 then
			bee.setText(self.TipsText, _T("LAB_SETTINGS_105"))
		elseif errCode == -704 then
			bee.setText(self.TipsText, _T("LAB_SETTINGS_106"))
		elseif errCode == -705 then
			bee.setText(self.TipsText, _T("LAB_SETTINGS_121"))
		else
			bee.setText(self.TipsText, _T("LAB_SETTINGS_102"))
		end
	end
	PlayerModel:requestRedeemCodeExchange(inputCode, succCb, errCb, limitCb)
end

return P