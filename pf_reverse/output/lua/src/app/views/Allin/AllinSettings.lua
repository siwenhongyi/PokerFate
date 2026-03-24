local P = class("AllinSettings", require("app.table.IngameSettings"))

function P:onAwake()
    P.super.onAwake(self)

    
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end)
end

