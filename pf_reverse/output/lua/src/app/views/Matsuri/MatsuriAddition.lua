local P = class("MatsuriAddition", Object)

function P:onAwake()
    local SelectButton = self:find("SelectButton")
    self.ImageIcon = self:find("Mask/ImageIcon", SelectButton)
    self.ItemIcon = self:find("Icon")
    self.Text1 = self:find("Text1")
    self.Text2 = self:find("Text2")

    bee.addClick(SelectButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-select", ActivityId.Matsuri, self._params.game_type)
        UiManager:showUI("MatsuriPlayer", {game_type = self._params.game_type, hideCb = function()
            self:refreshRole()
        end})
    end)

    local propIcon = self:find("Icon")
    bee.setIcon(propIcon, ThemeModel:getThemeIcon())
    bee.addClick(self.ItemIcon, function ()
        Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(ThemeModel:getItemId(), true), target = self.ItemIcon})
    end, true)

    self:refreshRole()
end

function P:refreshRole()
    local skinData = ThemeModel:getCurSkinAddData()
    if skinData then
        -- local skin = tpl_character_skin[skinData[1]]
        -- local role = skin.role
        CharacterModel:setSkinAvater(self.ImageIcon, skinData[1])
        self.ImageIcon:SetActive(true)
        self.Text1:SetActive(false)
        self.Text2:SetActive(true)
        bee.setText(self.Text2, "+" .. skinData[2] / 10 .. "%")
    else
        self.ImageIcon:SetActive(false)
        self.Text1:SetActive(true)
        self.Text2:SetActive(false)
    end
end

return P