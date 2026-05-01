local P = class("FriendsRoomByin", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)

    self.TextTitle = self:find("TextTitle", self.Panel)
    self.Slider = self:find("Slider", self.Panel)
    self.Handle = self:find("Handle", self.Slider)
    self.MinusButton = self:find("MinusButton", self.Panel)
    self.PlusButton = self:find("PlusButton", self.Panel)

    self.Buyin = self:find("Buyin", self.Panel)
    self.TextMin = self:find("TextMin", self.Panel)
    self.TextMax = self:find("TextMax", self.Panel)
    self.TextByin = self:find("TextByin", self.Panel)
    self.ImageArrow = self:find("ImageArrow", self.Panel)

    bee.addClick(self:find("StartButton", self.Panel), function()
        if self._params and self._params.isSetReby then
            Net:sendReq("pb.SetRebyREQ", {
                reby_chips = self._byins[self.ByinSlider:getCurStep()]
            })
        else
            Net:sendReq("pb.RebyREQ", {
                is_reby = true,
                chips = self._byins[self.ByinSlider:getCurStep()],
            })
        end
        self:hideUI()
    end)
    bee.addClick(self:find("CloseButton", self.Panel), function()
        if self._params and self._params.isSetReby then
        else
            Net:sendReq("pb.LeaveRoomREQ", {})
        end
        self:hideUI()
    end)
    bee.addClick(self.MinusButton, function()
        self.ByinSlider:setCurStep(self.ByinSlider:getCurStep() - 1, true)
    end)
    bee.addClick(self.PlusButton, function()
        self.ByinSlider:setCurStep(self.ByinSlider:getCurStep() + 1, true)
    end)
    -- bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
    --     Net:sendReq("pb.LeaveRoomREQ", {})
    --     self:hideUI()
    -- end, true)
end

function P:onShow()
    self._byins = {}
    for i = GameModel.data:getMinBuyIn(), GameModel.data:getMaxBuyIn(), GameModel.data:getBigBlind() * 10 do
        table.insert(self._byins, i)
    end
    if #self._byins == 1 then
        table.insert(self._byins, self._byins[1])
    end
    bee.setText(self.TextMin, _N(GameModel.data:getMinBuyIn()))
    bee.setText(self.TextMax, _N(GameModel.data:getMaxBuyIn()))

    self.ByinSlider = UiSliderEx:create(self.Slider)
    self.ByinSlider:onValueChanged(function(val)
        bee.setText(self.TextByin, _N(val))
        local pos = self.ImageArrow.transform.position
        pos.x = self.Handle.transform.position.x
        self.ImageArrow.transform.position = pos
        self:refreshButton()
    end, true)
    self.ByinSlider:setStepDatas(self._byins)

    self.ByinSlider:setCurStep(1, true)

    if self._params and self._params.isSetReby then
        if self._params.isSetReby then
            bee.setText(self.TextTitle, _T("LAB_GAME_026"))
            bee.setText(self:find("Text", self.StartButton), _T("LAB_GAME_027"))

            for k, v in ipairs(self._byins) do
                if v == GameModel.data:getDelayRebyChips() then
                    self.ByinSlider:setCurStep(k, true)
                    break
                end
            end
        end
    end
end

function P:refreshButton()
    self.MinusButton:SetActive(self.ByinSlider:getCurStep() > 1)
    self.PlusButton:SetActive(self.ByinSlider:getCurStep() < #self._byins)
end

function P:evt_DealerInfoRSP()
    if self._params and self._params.isSetReby then
        self:hideUI()
    end
end

function P:evt_TableGameOverRSP()
    if self._params and self._params.isSetReby then
        self:hideUI()
    end
end


return P