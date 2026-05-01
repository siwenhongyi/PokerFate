local P = class("HotSpringAddition", Object)

function P:onAwake()
    local SelectButton = self:find("SelectButton")
    self.ImageIcon = self:find("Mask/ImageIcon", SelectButton)
    self.Text1 = self:find("Text1")
    self.Text2 = self:find("Text2")

    bee.addClick(SelectButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("HotSpringHallPlayer", {hideCb = function()
            self:refreshRole()
        end})
    end)

    self:refreshRole()
end

function P:refreshRole()
    local role = ThemeModel:getCurRoleId()
    if role > 0 then
        CharacterModel:setSkinAvater(self.ImageIcon, CharacterModel:getRole(role):getUsingSkin())
        self.ImageIcon:SetActive(true)
        self.Text1:SetActive(false)
        self.Text2:SetActive(true)
        
        local data = tpl_theme_activity[ThemeModel:getConfId()]
        for i = 1, #data.player_add - 1, 2 do
            if data.player_add[i] == role then
                bee.setText(self.Text2, "+" .. data.player_add[i + 1] / 10 .. "%")
                break
            end
        end
    else
        self.ImageIcon:SetActive(false)
        self.Text1:SetActive(true)
        self.Text2:SetActive(false)
    end
end

return P