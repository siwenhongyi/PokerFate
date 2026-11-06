local P = class("FriendsRoomCreate", UiDialog)
local FRIENDS_GAME_TIMES = {5, 10, 20, 30}
local BLIND_STEP = 20

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)
    self.Create = self:find("Create", self.Panel)
    self.Content = self:find("CreateList/Viewport/Content", self.Panel)
    self.TextSNGTip = self:find("TextSNGTip", self.Panel)

    self.Game = self:find("Game", self.Content)
    self.Room = self:find("Room", self.Content)
    self.Seat = self:find("Seat", self.Content)
    self.Blinds = self:find("Blinds", self.Content)
    self.Buyin = self:find("Buyin", self.Content)
    self.Action = self:find("Action", self.Content)
    self.TableChat = self:find("TableChat", self.Content)
    self.SeenCard = self:find("SeenCard", self.Content)

    self.NormalViews = {
        self.Blinds,
        self.Buyin,
        self.Action,
    }

    self.GameFilter = self:find("Gameplay/GameFilter", self.Room)
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
    self.ToggleSeen = self:find("Switch", self.SeenCard)

    self.TimeToggles = {
        self:find("CheckToggle01", self.Action),
        self:find("CheckToggle02", self.Action),
        self:find("CheckToggle03", self.Action),
        self:find("CheckToggle04", self.Action),
    }
    for k, v in ipairs(FRIENDS_GAME_TIMES) do
        bee.setText(self:find("TextTime", self.TimeToggles[k]), _F("LAB_FRIROOM_009", v))
    end

    self:initSNGView()

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
        UiManager:showUI("LoadingLayer", {cb = function()
            self:onBtCreate()
        end})
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

    self.ByinSlider = UiSliderEx2:create(self.SliderByin)
    self.ByinSlider:onValueChanged(function(v1, v2)
        self._byinV1, self._byinV2 = v1, v2
        self:refreshByinText()
    end)

    self._filter_game_types = {
        GAME_GAME_TYPE.FRIEND_HOLDEM_GAME, 
        GAME_GAME_TYPE.FRIEND_OMAHA_GAME, 
        GAME_GAME_TYPE.FRIEND_SNG_GAME, 
    }
    self.Filter = UiFilterBox:create(self.GameFilter, self:find("FilteItem", self.GameFilter), self.node)
    self.Filter:setDatas({
        _T("LAB_POKER_GAME"),
        _T("LAB_OMAHA"),
        _T("LAB_SNG"),
    })
    self.Filter:setSelectFunc(function(idx, data)
        LocalStore:setIntegerForKey("Friend_Room_Create_Filter", idx)
        self:setCurGameType(self._filter_game_types[idx])
    end)

    self._defaultValues = {
        seat_num = 3,
        bb = 2,
        min_byin = 2,
        max_byin = 5,
        action_time = 2,
        is_forbid_chat = false,
        is_private = false,
        is_seen = false,
        

        blind = 1,
        up_blind_time = 2,
        add_time = 2,
    }

    self:resetByinStep(tpl_table_poker_friend_list)
end

function P:resetByinStep(list, values)
    values = values or self._defaultValues
    self.BlindSlider:setStepDatas(list)

    local d = list[1]
    self._byinSteps = {}
    self._byinV1, self._byinV2 = values.min_byin or 3, values.max_byin or 9
    local idx = 1
    for i = d.min_byin, d.max_byin, d.bb * BLIND_STEP do
        table.insert(self._byinSteps, idx)
        idx = idx + 1
    end
    self.ByinSlider:setStepDatas(self._byinSteps)
end

function P:initSNGView()
    self.SngChips = self:find("SngChips", self.Content)
    self.SngBlindTime = self:find("SngBlindTime", self.Content)
    self.SngBlind = self:find("SngBlind", self.Content)
    self.SngAction = self:find("SngAction", self.Content)
    self.SngAdd = self:find("SngAdd", self.Content)

    self.SngViews = {
        self.SngChips,
        self.SngBlindTime,
        self.SngBlind,
        self.SngAction,
        self.SngAdd,
    }

    self.SngBlindToggles = {
        self:find("CheckToggle01", self.SngBlind),
        self:find("CheckToggle02", self.SngBlind),
    }

    for k, v in ipairs(self.SngBlindToggles) do
        bee.onCheck(v, function(isOn)
            if isOn then
                bee.logEvent("friendsroom-sng-blindrules-type", k)
            end
        end)
    end

    bee.addClick(self:find("Title/InfoButton", self.SngBlind), function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("friendsroom-sng-blindrules")

        UiManager:showUI("FriendsRoomBlindStructure", {id = bee.isCheck(self.SngBlindToggles[1]) and 1 or 2})
    end)

    self.SngChipSlider = self:bindSlider(self.SngChips, tpl_constdata.Friend_SNG_Chips, "{p1}")
    self.SngBlindTimeSlider = self:bindSlider(self.SngBlindTime, tpl_constdata.Friend_SNG_Blindup, "LAB_TIME_MINUTES")
    self.SngActionSlider = self:bindSlider(self.SngAction, tpl_constdata.Friend_SNG_Basetime, "LAB_TIME_SECONDS")
    self.SngAddSlider = self:bindSlider(self.SngAdd, tpl_constdata.Friend_SNG_Timebank, "LAB_TIME_SECONDS")
end

function P:onShow()
    self.Filter:setSelectIdx(LocalStore:getIntegerForKey("Friend_Room_Create_Filter", 1))
    -- self:setCurGameType(self._filter_game_types[1])
end

function P:bindSlider(parent, datas, format)
    local MinusButton = self:find("MinusButton", parent)
    local PlusButton = self:find("PlusButton", parent)
    local slider = UiSliderEx:create(self:find("Slider", parent))
    slider:onValueChanged(function(val)
        bee.setText(self:find("Title/TextTime", parent), _F(format, _N(val)))
        PlusButton:SetActive(slider:getCurStep() < slider:getTotalStep())
        MinusButton:SetActive(slider:getCurStep() > 1)
    end)
    slider:setStepDatas(datas)

    bee.addClick(MinusButton, function()
        slider:setCurStep(slider:getCurStep() - 1, true)
    end)
    bee.addClick(PlusButton, function()
        slider:setCurStep(slider:getCurStep() + 1, true)
    end)

    return slider
end

function P:onBtCreate()
    if GF.isFriendSNG(self._game_type) then
        self:onBtCreateSNG()
    else
        self:onBtCreatePoker()
    end
end

function P:onBtCreatePoker()
    local d = self.BlindSlider:getCurData()
    local idx1, idx2 = self._byinSteps[self._byinV1] - 1, self._byinSteps[self._byinV2] - 1
    local req = {
        game_type = self._game_type,
        seat_num = self._seatNum,
        action_time = self:getActionTime(),
        is_forbid_chat = not bee.isCheck(self.ToggleChat),
        is_private = bee.isCheck(self.TogglePrivate),
        open_observer = self.SeenCard.activeSelf and bee.isCheck(self.ToggleSeen),

        bb = d.bb,
        min_byin = d.min_byin + idx1 * d.bb * BLIND_STEP,
        max_byin = d.min_byin + idx2 * d.bb * BLIND_STEP,
    }
    Net:sendReq("pb.CreateFriendRoomREQ", req)
    LocalStore:saveTableData(self.__cname .. self._game_type, {
        seat_num = req.seat_num,
        is_private = req.is_private,
        is_forbid_chat = req.is_forbid_chat,
        is_seen = req.open_observer,
        blind = req.blind_id,
        bb = self.BlindSlider:getCurStep(),
        action_time = self:getActionTimeStep(),
        min_byin = self._byinV1,
        max_byin = self._byinV2,
    })
end

function P:onBtCreateSNG()
    local d = self.BlindSlider:getCurData()
    local req = {
        game_type = self._game_type,
        seat_num = self._seatNum,
        is_forbid_chat = not bee.isCheck(self.ToggleChat),
        is_private = bee.isCheck(self.TogglePrivate),
        open_observer = bee.isCheck(self.ToggleSeen),

        blind_id = bee.isCheck(self.SngBlindToggles[1]) and 1 or 2,
        up_blind_time = tpl_constdata.Friend_SNG_Blindup[self.SngBlindTimeSlider:getCurStep()],
        think_time = tpl_constdata.Friend_SNG_Timebank[self.SngAddSlider:getCurStep()],
        begin_chips = tpl_constdata.Friend_SNG_Chips[self.SngChipSlider:getCurStep()],
        action_time = tpl_constdata.Friend_SNG_Basetime[self.SngActionSlider:getCurStep()],
    }
    Net:sendReq("pb.CreateFriendRoomREQ", req)
    LocalStore:saveTableData(self.__cname .. self._game_type, {
        seat_num = req.seat_num,
        is_private = req.is_private,
        is_forbid_chat = req.is_forbid_chat,
        is_seen = req.open_observer,
        blind = req.blind_id,
        bb = self.SngChipSlider:getCurStep(),
        up_blind_time = self.SngBlindTimeSlider:getCurStep(),
        action_time = self.SngActionSlider:getCurStep(),
        add_time = self.SngAddSlider:getCurStep(),
    })
end

function P:resetValues(values)
    values = values or self._defaultValues
    for k, v in pairs(self._defaultValues) do
        if nil == values[k] then
            values[k] = v
        end
    end

    if values.is_private then
        bee.setCheck(self.TogglePrivate, true, true)
    else
        bee.setCheck(self.TogglePublic, true, true)
    end
    bee.setCheck(self.ToggleChat, true, not values.is_forbid_chat)
    bee.setCheck(self.ToggleSeen, true, values.is_seen)
    self:setSeatNum(values.seat_num)

    if GF.isFriendSNG(self._game_type) then
        self.SngChipSlider:setCurStep(values.bb, true)
        self.SngBlindTimeSlider:setCurStep(values.up_blind_time, true)
        self.SngActionSlider:setCurStep(values.action_time, true)
        self.SngAddSlider:setCurStep(values.add_time, true)

        bee.setCheck(self.SngBlindToggles[values.blind], true)

        self.SeenCard:SetActive(true)
    else
        self.BlindSlider:setCurStep(values.bb, true)
        self.ByinSlider:setStep(values.min_byin, values.max_byin)
        bee.setCheck(self.TimeToggles[values.action_time])

        self.SeenCard:SetActive(true)
    end
end

function P:setSeatNum(num)
    local min = GF.isFriendSNG(self._game_type) and 2 or 3
    if num < min then
        num = min
    elseif num > 6 then
        num = 6
    end
    self._seatNum = num
    bee.setText(self.TextSeat, num)
    self.AddButtonSeat:SetActive(self._seatNum < 6)
    self.MinusButtonSeat:SetActive(self._seatNum > min)
end

function P:setCurGameType(gameType)
    self._game_type = gameType
    local isSng = GF.isFriendSNG(gameType)
    self.TextSNGTip:SetActive(isSng)
    for _, v in ipairs(self.SngViews) do
        v:SetActive(isSng)
    end
    for _, v in ipairs(self.NormalViews) do
        v:SetActive(not isSng)
    end

    local d = LocalStore:getTableData(self.__cname .. gameType)

    if GF.isFriendPoker(self._game_type) then
        self:resetByinStep(tpl_table_poker_friend_list, d)
    elseif GF.isFriendOmaha(self._game_type) then
        self:resetByinStep(tpl_table_omaha_friend_list, d)
    end
    self:resetValues(d)
end

function P:getActionTime()
    for k, v in ipairs(self.TimeToggles) do
        if bee.isCheck(v) then
            return FRIENDS_GAME_TIMES[k]
        end
    end
    return FRIENDS_GAME_TIMES[2]
end

function P:getActionTimeStep()
    for k, v in ipairs(self.TimeToggles) do
        if bee.isCheck(v) then
            return k
        end
    end
    return 2
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