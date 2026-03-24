local P = class("LoginUpdateDialog", UiBase)

function P:onAwake()
    local Panel = self:find("AnimRoot/Center/Panel")

    bee.addClick(self:find("ConfirmButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CancelButton", Panel), function()
        self:hideUI()
    end)

    bee.setText(self:find("TextTip", Panel), _F("LAB_UPDATE_TIP", "100M"))
end

