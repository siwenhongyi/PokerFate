local P = class("SchoolRules", UiDialog)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/Panel")
    self.CloseButton = self:find("Popup/school_btn_tc_close", self.Panel)
    self.MaskButton = self:find("AnimRoot/common_panel_mask_70", self.Panel)
    -- self.Content = self:find("ContentList/Viewport/Content/Event Duration")

    bee.addClick(self.CloseButton, function()
        self:hideUI()
    end)
    bee.addClick2(self.MaskButton, function()
        self:hideUI()
    end, true)
end

function P:onShow()

end

