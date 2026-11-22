local P = class("CharacterCollectCharacters", UiBase)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/Panel")
    self.ToggleCheck = self:find("character_bg_notice/ToggleCheck", self.Panel)
    self.TipsText = self:find("TipsText", self.Panel)

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)
    bee.addClick(self:find("CancelButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", self.Panel), function()
        if bee.isCheck(self.ToggleCheck) then
            SettingModel:setRoleShowStarDlg(false)
        end
        Net:sendReq("pb.RoleSetStarREQ", {role_id = self._params.role_id, is_star = not self._params.is_star})
        bee.logEvent("character-starred", self._params.role_id, is_star and 0 or 1)
        self:hideUI()
    end)
end

function P:onStart()
    if self._params and self._params.role_id then
        local role = CharacterModel:getRole(self._params.role_id)
        if role:isTrial() then
            bee.setText(self.TipsText, _T("LAB_CHAR_139"))
        else
            bee.setText(self.TipsText, _T("LAB_CHAR_092"))
        end
    end
end

return P