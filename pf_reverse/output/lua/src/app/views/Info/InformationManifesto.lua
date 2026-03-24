local P = class("InformationManifesto", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)

    self.TextNum = self:find("TextNum", self.Panel)
    self.InputFieldCxt = self:find("InputFieldCxt", self.Panel)

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end)
    bee.addClick(self:find("SaveButton", self.Panel), function()
        local dec = bee.getText(self.InputFieldCxt, "InputField")
        Net:post("/player/updateDeclaration", {declaration = GF:getValidString(dec)}, function(d)
            if 0 == d.code then
                PlayerModel._declaration = dec
                self:hideUI()
                UiManager:showToast(_T("LAB_FRIENDS_21"))
                bee.emit(EventDef.evt_refreshDeclaration)
            end
        end)
    end)
    bee.addClick(self:find("CancelButton", self.Panel), function()
        self:hideUI()
    end)
end

function P:onShow()
    local txt = PlayerModel:getDeclaration()
    bee.setText(self.InputFieldCxt, txt, "InputField")
    bee.setText(self.TextNum, string.format("%d/140", string.utf8len2(txt)))
    self.InputFieldCxt:GetComponent("InputField").onValueChanged:AddListener(function(str)
        local curLen = string.utf8len2(str)
        if curLen <= tpl_constdata.DeclarationLimit then
            bee.setText(self.TextNum, string.format("%d/%d", string.utf8len2(str), tpl_constdata.DeclarationLimit))
            txt = str
        else
            bee.setText(self.InputFieldCxt, txt, "InputField")
        end
    end)
end

