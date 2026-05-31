local P = class("DecorationPanel", UiBase)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")
    self.EditGo = self:find("Edit", Center)
    self.ConfirmButton = self:find("ConfirmButton", self.EditGo)
    self.ResetButton = self:find("ResetButton", self.EditGo)
    self.InputField = self:find("InputField", self.EditGo)
    self.CloseButton = self:find("CloseButton", self.EditGo)

    self.HintGo = self:find("Hint", Center)
    self.TipConfirmButton = self:find("ConfirmButton", self.HintGo)
    self.TipCancelButton = self:find("CancelButton", self.HintGo)
    self.TipCloseButton = self:find("CloseButton", self.HintGo)


    bee.addClick(self.CloseButton, function ()
        Game:playSound("ui_button_confirm")
        self:hideUI()
    end)
    bee.addClick(self.ConfirmButton, function ()
        Game:playSound("ui_button_confirm")
        self:EditorSchemeName()
    end)
    bee.addClick(self.ResetButton, function ()
        Game:playSound("ui_button_confirm")
        self:ResetSchemeName()
    end)
end

function P:onShow()
    self.schemeId = self._params.id
    self.oriName = self._params.name
end

function P:EditorSchemeName()
    local name = bee.getText(self.InputField, "InputField")
    
	local n = string.utf8len2(name)
	if n < 2 or n > 16 then
		UiManager:showError(_T("LAB_INFO_016"))
        return
    end
    if name == "" then
        return
    end
    if self.schemeId then
        DecorationModel:changeSchemeName(name, self.schemeId)
    else
        bee.emit("evt_changeNewSchemeNameCallback", {name = name})
        self:hideUI()
    end
end
function P:ResetSchemeName()
    bee.setText(self.InputField, self.oriName, "InputField")
    UiManager:showToast(_T("LAB_DECOR_PLAN_TIPS_6"))
end

function P:evt_changeSchemeNameCallback()
    self:hideUI()
    UiManager:showToast(_T("LAB_DECOR_PLAN_TIPS_7"))
end

return P