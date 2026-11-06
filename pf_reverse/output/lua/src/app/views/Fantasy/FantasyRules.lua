local P = class("FantasyRules", UiDialog)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/panel")
    self.CloseButton = self:find("fantasy_button_close", self.Panel)
    self.MaskButton = self:find("AnimRoot/common_panel_mask_70")
    self.Content = self:find("ContentList/Viewport/Content/Event Duration", self.Panel)

    bee.addClick(self.CloseButton, function()
        self:hideUI()
    end)
    bee.addClick2(self.MaskButton, function()
        self:hideUI()
    end, true)

    -- local posY = LanguageManager:getLanguage() == "en" and 247 or 260.5
    -- self:find("Title", self.Panel).transform.localPosition = bee.v3(-32, posY, 0)
end

function P:onShow()
    local index = ThemeModel:getSkinAddEffectIndex()
    local data = tpl_theme_activity[ThemeModel:getConfId()]
    local strId = data.rules[index]
    bee.setText(self.Content, _T(strId))
end

return P