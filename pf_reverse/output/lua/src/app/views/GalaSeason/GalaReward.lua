local P = class("GalaReward", Object)

function P:onAwake()
    bee.addClick(self:find("Icon"), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = {item_id = 10410002}, target = self:find("Icon")})
    end)

end


