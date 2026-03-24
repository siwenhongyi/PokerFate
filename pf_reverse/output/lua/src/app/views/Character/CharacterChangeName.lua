local P = class("CharacterChangeName", UiDialog)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")
    local Panel = self:find("Panel", Center)

    self.NameInput = self:find("NameInput", Panel)

    bee.addClick(self:find("CloseButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", Panel), function()
        local name = bee.getText(self.NameInput, "InputField")
        if not GF.isValidName(name) then
            return
        end
        Game:playSound("ui_button_confirm")
        if name == _T(self._selectData.info.name) then
            -- Net:sendReq("pb.RoleRenameREQ", {role_id = self._selectData.role_id, name = ""})
            self:reqChangeName("")
        else
            -- Net:sendReq("pb.RoleRenameREQ", {role_id = self._selectData.role_id, name = name})
            self:reqChangeName(name)
        end
        -- self:hideUI()
    end)
    bee.addClick(self:find("CancelButton", Panel), function()
        Game:playSound("ui_button_confirm")
        bee.setText(self.NameInput, _T(self._selectData.info.name), "InputField")
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end)
end

function P:onShow()
    self._selectData = self._params.data
    bee.logEvent("character-editname", self._params.from == "CharacterMainProfile" and 2 or 1)
end

function P:reqChangeName(name)
    Net:post("/role/updateNickname", {
        role_id = self._selectData.role_id,
        nickname = GF:getValidString(name),
    }, function(d)
        if 0 == d.code then
            local msg = {
                code = 0,
                role_id = self._selectData.role_id,
                name = name,
            }
            net:RoleRenameRSP(msg)
            self:hideUI()
            bee.emit("evt_RoleRenameRSP", msg)
        end
    end)
end

