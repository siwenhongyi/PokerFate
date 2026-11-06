local P = class("TournamentMTTBlindStructure", UiBase)

function P:onAwake()
    self._closeAnim = "UI_1_TournamentBlindStructure_back"

    self.AnimRoot = self:find("AnimRoot")
    self.Right = self:find("Right", self.AnimRoot)

    self.SidePanel = self:find("SidePanel", self.Right)
    self.InfoButton = self:find("InfoButton", self.SidePanel)

    bee.addClick(self:find("TouchMask", self.AnimRoot), function()
        self:hideUI()
    end)
    bee.addClick(self:find("SideButton", self.SidePanel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("InfoButton", self.SidePanel), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("TournamentMTTBlindTip", {data = self._params.data, target = self:find("InfoButton", self.SidePanel)})
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
        self.ListBlind:setDatas(self._params.data.blind_list)
    end
end

function P:refreshBlindItem(data, item)
    bee.setText(self:find("TextLevel", item), data.blind_level)
    bee.setText(self:find("TextBlind", item), _N(data.small_blind) .. "/" .. _N(data.big_blind))
    bee.setText(self:find("TextAnte", item), _N(data.ante))

    self:find("tournament_sng_details_blind_list_frame_01", item):SetActive(data.blind_level % 2 == 1)
    self:find("tournament_sng_details_blind_list_frame_02", item):SetActive(data.blind_level % 2 == 0)

    self:find("icon/tournament_ingame_blind_icon_rebuy", item):SetActive(self._params.data.can_reby and data.blind_level <= self._params.data.late_reg_level)
    self:find("icon/tournament_ingame_blind_icon_addon", item):SetActive(self._params.data.can_addon and data.blind_level == self._params.data.late_reg_level)
end

return P