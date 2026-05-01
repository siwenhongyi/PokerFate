local P = class("CharacterBaseNameCard", UiFullView)

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    local LeftBottom = self:find("LeftBottom", AnimRoot)
    
    self.NameCard = self:find("NameCard", LeftBottom)
    if self.NameCard then
        self.TextName = self:find("TextName", self.NameCard)
        self.TextCV = self:find("TextCV", self.NameCard)
    end

    if self.NameCard then
        self.character_name_card_edit = self:find("character_name_card_edit", self.NameCard)
        bee.addClick(self.character_name_card_edit, function()
            Game:playSound("ui_button_confirm")
            UiManager:showUI("CharacterChangeName", {data = self._role, from = self.__cname})
        end)
    end
end

function P:refreshName()
    if self._role and self.TextName then
        local d = tpl_character[self._role.role_id]
        bee.setTextCut(self.TextName, self._role:getName(), self._nameLen or 386)
        bee.setText(self.TextCV, "CV: " .. _T(d.cv))

        if self.character_name_card_edit then
            self.character_name_card_edit:SetActive(not self._role.locked)
        end
    end
end

function P:evt_RoleRenameRSP(msg)
    self:refreshName()
end

return P