local P = class("FriendsRoomCreate", UiDialog)
local FRIENDS_GAME_TIMES = {5, 10, 20, 30}
local BLIND_STEP = 20

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)
    self.Create = self:find("Create", self.Panel)
    self.Content = self:find("CreateList/Viewport/Content", self.Panel)

    self.Game = self:find("Game", self.Content)
    self.Room = self:find("Room", self.Content)
    self.Seat = self:find("Seat", self.Content)
    self.Blinds = self:find("Blinds", self.Content)
    self.Buyin = self:find("Buyin", self.Content)
    self.Action = self:find("Action", self.Content)
    self.TableChat = self:find("TableChat", self.Content)

    self.TextSeat = self:find("TextSeat", self.Seat)
    self.TogglePrivate = self:find("TogglePrivate", self.Room)
    self.TogglePublic = self:find("TogglePublic", self.Room)
    self.AddButtonSeat = self:find("PlusButton", self.Seat)
    self.MinusButtonSeat = self:find("MinusButton", self.Seat)

    self.TextBlind = self:find("Blind/TextBlind", self.Blinds)
    self.SliderBlind = self:find("Slider", self.Blinds)
    self.AddButtonBlind = self:find("PlusButton", self.Blinds)
    self.MinusButtonBlind = self:find("MinusButton", self.Blinds)

    self.TextByin = self:find("Buyin/TextByin", self.Buyin)
    self.SliderByin = self:find("Slider", self.Buyin)
    self.TextMinByin = self:find("TextMinByin", self.Buyin)
    self.TextMaxByin = self:find("TextMaxByin", self.Buyin)

    self.ToggleChat = self:find("Switch", self.TableChat)

    self.TimeToggles = {
        self:find("CheckToggle01", self.Action),
        self:find("CheckToggle02", self.Action),
        self:find("CheckToggle03", self.Action),
        self:find("CheckToggle04", self.Action),
    }
    for k, v in ipairs(FRIENDS_GAME_TIMES) do
        bee.setText(self:find("TextTime", self.TimeToggles[k]), _F("LAB_FRIROOM_009", v))
    end

    bee.addClick(self.AddButtonSeat, function()
        self:setSeatNum(self._seatNum + 1)
    end)
    bee.addClick(self.MinusButtonSeat, function()
        self:setSeatNum(self._seatNum - 1)
    end)

    bee.addClick(self.AddButtonBlind, function()
        self.BlindSlider:setCurStep(self.BlindSlider:getCurStep() + 1, true)
    end)
    bee.addClick(self.MinusButtonBlind, function()
        self.BlindSlider:setCurStep(self.BlindSlider:getCurStep() - 1, true)
    end)

    bee.addClick(self:find("CreateButton", self.Panel), function()
        if not bee.checkCd("FRIENDS_ROOM_CREATE_REQ_CREATE", 1) then
            return
        end
        local d = self.BlindSlider:getCurData()
        local idx1, idx2 = self._byinSteps[self._byinV1] - 1, self._byinSteps[self._byinV2] - 1
        Net:sendReq("pb.CreateFriendRoomREQ", {
            game_type = GAME_GAME_TYPE.FRIEND_HOLDEM_GAME,
            seat_num = self._seatNum,
            bb = d.bb,
            min_byin = d.min_byin + idx1 * d.bb * BLIND_STEP,
            max_byin = d.min_byin + idx2 * d.bb * BLIND_STEP,
            action_time = self:getActionTime(),
            is_forbid_chat = not bee.isCheck(self.ToggleChat),
            is_private = bee.isCheck(self.TogglePrivate),
        })
    end)
    bee.addClick(self:find("ResetButton", self.Panel), function()
        self:resetValues()
    end)
    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)

    self.BlindSlider = UiSliderEx:create(self.SliderBlind)
    self.BlindSlider:onValueChanged(function(val)
        bee.setText(self.TextBlind, "" .. _N(val.sb) .. "/" .. _N(val.bb))
        self:refreshBlindButton()
    end)
    self.BlindSlider:setStepDatas(tpl_table_poker_friend_list)

    self.ByinSlider = UiSliderEx2:create(self.SliderByin)
    self.ByinSlider:onValueChanged(function(v1, v2)
        self._byinV1, self._byinV2 = v1, v2
        self:refreshByinText()
    end)
    local d = tpl_table_poker_friend_list[1]
    self._byinSteps = {}
    self._byinV1, self._byinV2 = 3, 9
    local idx = 1
    for i = d.min_byin, d.max_byin, d.bb * BLIND_STEP do
        table.insert(self._byinSteps, idx)
        idx = idx + 1
    end
    self.ByinSlider:setStepDatas(self._byinSteps)
end

function P:onShow()
    self:resetValues()
end

function P:resetValues()
    self.BlindSlider:setCurStep(2, true)
    self:setSeatNum(3)
    self.ByinSlider:setStep(2, 5)
    bee.setCheck(self.TimeToggles[2], true)
    bee.setCheck(self.TogglePublic, true)
    bee.setCheck(self.ToggleChat, true)
end

function P:setSeatNum(num)
    if num < 2 then
        num = 2
    elseif num > 6 then
        num = 6
    end
    self._seatNum = num
    bee.setText(self.TextSeat, num)
    self.AddButtonSeat:SetActive(self._seatNum < 6)
    self.MinusButtonSeat:SetActive(self._seatNum > 2)
end

function P:getActionTime()
    for k, v in ipairs(self.TimeToggles) do
        if bee.isCheck(v) then
            return FRIENDS_GAME_TIMES[k]
        end
    end
    return FRIENDS_GAME_TIMES[2]
end

function P:refreshBlindButton()
    self.AddButtonBlind:SetActive(self.BlindSlider:getCurStep() < self.BlindSlider:getTotalStep())
    self.MinusButtonBlind:SetActive(self.BlindSlider:getCurStep() > 1)

    local d = self.BlindSlider:getCurData()
    bee.setText(self.TextMinByin, _N(d.min_byin))
    bee.setText(self.TextMaxByin, _N(d.max_byin))

    self:refreshByinText()
end

function P:refreshByinText()
    local idx1, idx2 = self._byinSteps[self._byinV1] - 1, self._byinSteps[self._byinV2] - 1
    local d = self.BlindSlider:getCurData()
    bee.setText(self.TextByin, "" .. _N(d.min_byin + idx1 * d.bb * BLIND_STEP) .. "/" .. _N(d.min_byin + idx2 * d.bb * BLIND_STEP))
end

return P