local P = class("TournamentBlindStructure", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Right = self:find("Right", self.AnimRoot)

    self.SidePanel = self:find("SidePanel", self.Right)

    bee.addClick(self:find("TouchMask", self.AnimRoot), function()
        self:hideUI()
    end)
    bee.addClick(self:find("SideButton", self.SidePanel), function()
        self:hideUI()
    end)

    local BlindList = self:find("BlindList", self.SidePanel)
    local Item1 = self:find("Item1", BlindList)
    Item1:SetActive(false)
    self.ListBlind = UiListEx:create(BlindList)
    self.ListBlind:setWidth(54)
    self.ListBlind:setCreateFunc(function()
        return CU.GameObject.Instantiate(Item1)
    end)
    self.ListBlind:setRefreshFunc(function(data, item)
        self:refreshBlindItem(data, item)
    end)

end

function P:onShow()
    if self._params and self._params.data then
        self.ListBlind:setDatas(self._params.data)
    else
        self.ListBlind:setDatas({
            {blind_level = 1, small_blind = 50, big_blind = 100, ante = 0, duration = 300},
            {blind_level = 2, small_blind = 75, big_blind = 150, ante = 0, duration = 300},
            {blind_level = 3, small_blind = 100, big_blind = 200, ante = 25, duration = 300},
            {blind_level = 4, small_blind = 150, big_blind = 300, ante = 25, duration = 300},
            {blind_level = 5, small_blind = 200, big_blind = 400, ante = 50, duration = 300},
            {blind_level = 6, small_blind = 300, big_blind = 600, ante = 50, duration = 300},
            {blind_level = 7, small_blind = 400, big_blind = 800, ante = 75, duration = 300},
            {blind_level = 8, small_blind = 500, big_blind = 1000, ante = 100, duration = 300},
        })
    end
end

function P:refreshBlindItem(data, item)
    bee.setText(self:find("TextLevel", item), data.blind_level)
    if data.ante > 0 then
        bee.setText(self:find("TextBlind", item), _N(data.small_blind) .. "/" .. _N(data.big_blind) .. "(" .. _N(data.ante) .. ")")
    else
        bee.setText(self:find("TextBlind", item), _N(data.small_blind) .. "/" .. _N(data.big_blind))
    end
    bee.setText(self:find("TextAnte", item), TimeHelp:getTimeLeftStr(data.duration, true))

    self:find("tournament_sng_details_blind_list_frame_01", item):SetActive(data.blind_level % 2 == 1)
    self:find("tournament_sng_details_blind_list_frame_02", item):SetActive(data.blind_level % 2 == 0)
end

return P