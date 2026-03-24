local P = class("ActivitySignInRetroactive", UiDialog)

function P:onAwake()
	local Notice = self:find("AnimRoot/Center/Notice")

	self.CountText = self:find("CountText", Notice)
	self.ConfirmButton = self:find("ConfirmButton", Notice)
	self.CancelButton = self:find("CancelButton", Notice)
	self.CloseButton = self:find("CloseButton", Notice)

	bee.addClick(self.ConfirmButton, function()
		self:onClickRetroactive()
	end)
	bee.addClick(self.CancelButton, function()
		self:hideUI()
	end)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
end

function P:onStart()
	bee.setText(self.CountText, _F("LAB_DAILY_SIGN_IN_9", SignInModel:getCanRetroactiveTimes(), SignInModel:getTotalCanRetroactiveTimes()))
end

-- 补签
function P:onClickRetroactive()
	SignInModel:sendSignIn(self._params.day)
end

function P:evt_ActivitySignIn()
	self:hideUI()
end

