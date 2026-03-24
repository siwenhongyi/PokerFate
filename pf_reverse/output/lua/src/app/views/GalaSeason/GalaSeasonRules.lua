local P = class("GalaSeasonRules", UiBase)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/Panel")

    bee.addClick(self:find("Popup/GalaSeason_btn_tc_close", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)
end

function P:onShow()
    bee.logEvent("galaseason-rules")
end

