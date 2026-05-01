local P = class("InformationRename", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)

    self.InputFieldName = self:find("InputFieldName", self.Panel)
    self.TextTip = self:find("TextTip", self.Panel)
    self.TextOwn = self:find("TextOwn", self.Panel)
    self.Item1 = self:find("Item1", self.Panel)
    self.TextNum = self:find("TextNum", self.Item1)

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", self.Panel), function()
        bee.setText(self.TextTip, "")
        local name = bee.getText(self.InputFieldName, "InputField")
        if not GF.isValidName(name, self.TextTip) then
            return
        end
        if ItemModel:getItemNumById(GPropId.ChangeName) <= 0 then
            local d = tpl_props[GPropId.ChangeName]
            UiManager:showTip({
                text = _T("LAB_INFO_022"),
                onSure = function()
                    ItemModel:jumpView(d.accesses[1], GPropId.ChangeName)
                    -- GF.gotoShop(function()
                    --     if ItemModel:getItemNumById(GPropId.ChangeName) > 0 then
                    --         self:reqChangeName(name)
                    --     end
                    -- end)
                end,
            })
        else
            self:reqChangeName(name)
        end
    end)
end

function P:onShow()
    bee.setText(self.TextTip, "")
    PropItem:create(self.Item1, ItemModel:getItem(GPropId.ChangeName, true)):bindTips()
    self:evt_ItemChangeRSP()
end

function P:reqChangeName(name)
    Net:post("/player/updateNickname", {nickname = GF:getValidString(name)}, function(d)
        if 0 == d.code then
            PlayerModel:setName(name)
            self:hideUI()
            UiManager:showToast(_T("LAB_INFO_021"))
            bee.emit(EventDef.evt_refreshName)
        else
            local e = tpl_errorCode[d.code]
            if e and e.tip ~= 0 then
                bee.setText(self.TextTip, _T(e.id))
            end
        end
    end, nil, true)
end

function P:evt_ItemChangeRSP(msg)
    -- bee.setText(self.TextOwn, _T("LAB_INFO_014") .. ItemModel:getItemNumById(GPropId.ChangeName))
    local num = ItemModel:getItemNumById(GPropId.ChangeName)
    if num >= 1 then
        bee.setText(self.TextNum, "" ..1 .. "/" .. num)
    else
        bee.setText(self.TextNum, _F("LAB_CHAR_068", 1, num))
    end
end

return P