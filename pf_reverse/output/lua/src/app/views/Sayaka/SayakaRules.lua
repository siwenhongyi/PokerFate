local P = class("SayakaRules", UiDialog)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/Panel")
    self.CloseButton = self:find("sayaka_tc_btn_close", self.Panel)
    self.MaskButton = self:find("AnimRoot/common_panel_mask_70")
    self.Content = self:find("ContentList/Viewport/Content/Event Duration", self.Panel)

    bee.addClick(self.CloseButton, function()
        self:hideUI()
    end, true)
    bee.addClick(self.MaskButton, function()
        self:hideUI()
    end, true)
end

function P:onShow()
    local index = ThemeModel:getSkinAddEffectIndex()
    local data = tpl_theme_activity[ThemeModel:getConfId()]
    local strId = data.rules[index]
    bee.setText(self.Content, _T(strId))
end

return P