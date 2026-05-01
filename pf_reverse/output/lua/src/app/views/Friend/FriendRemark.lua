local P = class("FriendRemark", UiDialog)

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")
	local Panel = self:find("Center/Panel", self.AnimRoot)

	self.TipsText = self:find("TipsText", Panel)
	self.Input = self:find("Input", Panel)
	self.ConfirmButton = self:find("ConfirmButton", Panel)
	self.RecoverButton = self:find("RecoverButton", Panel)
	self.CloseButton = self:find("CloseButton", Panel)

	self.Input:GetComponent("InputField").characterLimit = 8

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.ConfirmButton, function()
		self:onClickConfirm()
	end)
	bee.addClick(self.RecoverButton, function()
		self:onClickRecoverButton()
	end)
end

function P:onStart()
	self._data = self._params.data

	bee.setText(self.TipsText, _F("LAB_FRIENDS_15", self._data.nickname))

	if self._data.mark then
		bee.setText(self.Input, self._data.mark, "InputField")
	end
end

function P:onClickConfirm()
	local markText = bee.getText(self.Input, "InputField")
	if markText == "" then
		UiManager:showToast(_T("LAB_FRIENDS_20"))
		return
	end
	FriendModel:remarkFriend(self._data.uid, markText, function()
		UiManager:showToast(_T("LAB_FRIENDS_21"))
		self:hideUI()
	end)
end

function P:onClickRecoverButton()
	FriendModel:remarkFriend(self._data.uid, "", function()
		UiManager:showToast(_T("LAB_FRIENDS_19"))
		self:hideUI()
	end)
end

return P