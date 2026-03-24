local P = class("LoginSetPasswordDialog", require("app.views.Login.LoginBase"))

function P:onAwake()
    local Panel = self:find("AnimRoot/Center/Panel")
    self.InputFieldName = self:find("InputFieldName", Panel)
    self.TextTitle = self:find("TextTitle", Panel)
    self.TipsText = self:find("TipsText", Panel)

    bee.addClick(self:find("CloseButton", Panel), function()
        self:onClickClose()
    end)
    
    bee.addClick(self:find("ButtonBack", Panel), function()
        self:onClickClose()
    end)

    bee.addClick(self:find("ButtonOk", Panel), function()
        Game:playSound("ui_button_confirm")
        self:onClickConfirm()
    end)
end

function P:onStart()
    if self._params and self._params.reset then
        bee.setText(self.TextTitle, _T("LAB_RESET_PWD"))
    else
        bee.setText(self.TextTitle, _T("LAB_SET_PWD"))
    end
    self:initInputSeek(self.InputFieldName, false)
end

function P:onClickClose()
    self:hideUI()
    if self._params and self._params.closeCb then
        self._params.closeCb()
    else
        UiManager:showUI("LoginRegisterDialog", self._params)
    end
end

function P:onClickConfirm()
    local pw = bee.getText(self.InputFieldName, "InputField")
    
    if not GF.isValidPassword(pw) then
        bee.setText(self.TipsText, _T("HTTP_INVALID_EMAIL_PASSWORD_FORMAT"))
        return
    end

    if self._params and self._params.clickCb then
        self._params.clickCb(pw)
    end
    self:hideUI()
end

