local P = class("FriendsRoomBlindStructure", UiBase)

function P:onAwake()
    self._closeAnim = "UI_1_TournamentBlindStructure_back"
    self.AnimRoot = self:find("AnimRoot")
    self.Right = self:find("Right", self.AnimRoot)

    self.SidePanel = self:find("SidePanel", self.Right)

    self.TABS = {
        self:find("TAB/Toggle1", self.SidePanel),
        self:find("TAB/Toggle2", self.SidePanel),
    }

    for k, v in ipairs(self.TABS) do
        bee.onCheck(v, function(isOn)
            if isOn then
                self._id = k
                self:refreshUI()
            end
        end)
    end

    bee.addClick(self:find("TouchMask", self.AnimRoot), function()
        self:hideUI()
    end)
    bee.addClick(self:find("SideButton", self.SidePanel), function()
        self:hideUI()
    end)
    bee.addClick(self.InfoButton, function()
        Game:playSound("ui_button_confirm")
        if self._params and self._params.infoCb then
            self._params.infoCb()
        end
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
    self._id = self._params and self._params.id or 1
    
    bee.setCheck(self.TABS[self._id])
    self:refreshUI()
end

function P:refreshUI()
    local datas = 1 == self._id and tpl_blind1_list or tpl_blind2_list
    self.ListBlind:setDatas(datas)
end

function P:refreshBlindItem(data, item)
    bee.setText(self:find("TextLevel", item), data.id)
    if data.ante > 0 then
        bee.setText(self:find("TextBlind", item), _N(data.sb) .. "/" .. _N(data.bb) .. " (" .. _N(data.ante) .. ")")
    else
        bee.setText(self:find("TextBlind", item), _N(data.sb) .. "/" .. _N(data.bb))
    end

    self:find("tournament_sng_details_blind_list_frame_01", item):SetActive(data.id % 2 == 1)
    self:find("tournament_sng_details_blind_list_frame_02", item):SetActive(data.id % 2 == 0)
end

return P