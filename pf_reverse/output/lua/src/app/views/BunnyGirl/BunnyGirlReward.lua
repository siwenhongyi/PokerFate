local P = class("BunnyGirlReward", Object)

function P:onAwake()
    local cfg = ThemeModel:getConfData()

    local propIcon = self:find("Icon")
    bee.setIcon(propIcon, ThemeModel:getThemeIcon())

    bee.addClick(self:find("Icon"), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = {item_id = cfg.activity_item}, target = self:find("Icon")})
    end)

end


return P