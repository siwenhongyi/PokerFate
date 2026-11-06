local P = class("IngameIntensity", Object)


function P:onAwake()
    self.MaskButton = self:find("Mask")
    self.MaskBottomButton = self:find("MaskBottom")
    self.Select = self:find("Left/Select")

    self.Order = self:find("Left/Order")
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

    bee.addClick(self.MaskButton, function ()
        -- self:hideUI()
        CU.GameObject.Destroy(self.node)
    end)
    -- bee.addClick(self.MaskBottomButton, function ()
    --     self:hideUI()
    -- end)
end

function P:onStart()
    self:initCard()
    self:refreshSelect()
end

function P:initCard()
    local cardTypeCount = self.Order.transform.childCount
    for i = 1, cardTypeCount do
        local cardTypeItem = self.Order.transform:GetChild(i - 1)
        local cardTypeData = self.cardTypeList[i]
        local pokerCount = cardTypeItem.childCount
        for j = 1, pokerCount do
            local pokerItem = cardTypeItem:GetChild(j - 1)
            local data = cardTypeData[j]
            local img = GF.getCardImage(data[2], data[1])
            bee.setIcon(pokerItem, img)
        end
    end
end

function P:evt_refresh_intensity_cardtype()
    self:refreshSelect()
end
function P:evt_RoundOverBRC()
    self:refreshSelect()
end
function P:evt_TableGameOverRSP()
    self:refreshSelect()
end

function P:refreshSelect()
    local cardType = GameModel.data:getMyCardType()
    if cardType == nil then
        self.Select:SetActive(false)
        return
    end
    self.Select:SetActive(true)
    self.Select.transform.localPosition = bee.v3(self.Select.transform.localPosition.x, 341 - (59.5 * (10 - cardType)))
end

-- function P:evt_gameBlur(flag, name)
--     self:evt_uiBlur(flag, name)
-- end

return P