local P = class("LoginNoNetwordDialog", UiBase)

function P:onAwake()
    self.inPop = true
    local Center = self:find("AnimRoot/Center")
    local Network = self:find("Network", Center)
    self.Text = self:find("Text", Network)

    bee.addClick(self:find("Panel/CloseButton", Center), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", Network), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CopyButton", Network), function()
        CS.SdkHelper.copyText(SdkHelper:getDeviceID())
        UiManager:showToast(_T("LAB_COPY_SUC"))
    end)

    local id = SdkHelper:getDeviceID()
    id = string.sub(id, 1, 20) .. "******"
    bee.setText(self:find("TextEquipID", Network), _T("LAB_EQUIPMENT_ID") .. id)
end

function P:onShow()
    if self._params and self._params.text then
        bee.setText(self.Text, self._params.text)
    end
end

