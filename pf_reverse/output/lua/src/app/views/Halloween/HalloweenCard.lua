local P = class("HalloweenCard", UiDialog)

function P:onAwake()
    self.Pannel = self:find("AnimRoot/Center/Pannel")

    self.ScrollView = self:find("ScrollView", self.Pannel)
    self.ScrollRoot = self:find("Viewport/Content", self.ScrollView)

    self.CloseButton = bee.addClick(self:find("CloseButton", self.Pannel), function ()
        Game:playSound("ui_button_confirm")
        self:hideUI()
    end)


    self.cardTypeList = {
        [1] = {{"s", "a"}, {"s", "k"}, {"s", "q"}, {"s", "j"}, {"s", "10"}},
        [2] = {{"h", "j"}, {"h", "10"}, {"h", "9"}, {"h", "8"}, {"h", "7"}},
        [3] = {{"s", "a"}, {"h", "a"}, {"c", "a"}, {"d", "a"}, {"c", "10"}},
        [4] = {{"s", "k"}, {"h", "k"}, {"c", "k"}, {"h", "10"}, {"c", "10"}},
        [5] = {{"h", "a"}, {"h", "k"}, {"h", "9"}, {"h", "8"}, {"h", "6"}},
        [6] = {{"c", "10"}, {"h", "9"}, {"d", "8"}, {"h", "7"}, {"s", "6"}},
        [7] = {{"s", "q"}, {"h", "q"}, {"c", "q"}, {"d", "a"}, {"c", "10"}},
        [8] = {{"s", "a"}, {"h", "a"}, {"s", "q"}, {"h", "q"}, {"c", "10"}},
        [9] = {{"s", "q"}, {"h", "q"}, {"h", "8"}, {"s", "7"}, {"s", "5"}},
        [10] = {{"s", "a"}, {"d", "q"}, {"c", "10"}, {"h", "8"}, {"c", "5"}},
    }
end

function P:onShow()
    self:initCardType()
end

function P:initCardType()
    local count = #self.cardTypeList
    for i = 1, count do
        local data = self.cardTypeList[i]
        local cardType = 11 - i
        local item = self.ScrollRoot.transform:GetChild(i - 1)
        local lv = self:find("Level/Value", item)
        local lvVal = BalBattleModel.cardTypeLv[cardType]
        bee.setText(lv, lvVal)
        local cards = self:find("Cards", item)
        for j = 1, 5 do
            local card = cards.transform:GetChild(j - 1)
            local cardData = data[j]
            local img = GF.getCardImage(cardData[2], cardData[1])
            bee.setIcon(card, img)
        end
        bee.setText(self:find("Text", item), _T(POKER_TYPE_NAME[cardType]))
        local lvCfg = BalBattleModel:getCardTypeLvId(cardType, lvVal)
        bee.setText(self:find("Integral/chip", item), lvCfg.scores)
        bee.setText(self:find("Integral/power", item), lvCfg.multiple)
    end
end

return P