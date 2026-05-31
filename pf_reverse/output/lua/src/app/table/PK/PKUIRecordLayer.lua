local P = class("PKUIRecordLayer", UiBlurBase)

function P:onAwake()
    local Repaly = self:find("Repaly")
    self.LeftTop = self:find("LeftTop")
    self.TextTitle = self:find("ReplayInfo/TextTitle")
    self.TextTag = self:find("TextTag", Repaly)
    self.ImageTag = self:find("ImageTag", Repaly)
    self.TextName = self:find("TextName", Repaly)
    self.ButtonLeft = self:find("ButtonLeft", Repaly)
    self.ButtonRight = self:find("ButtonRight", Repaly)
    self.PauseButton = self:find("PauseButton", Repaly)
    self.PlayButton = self:find("PlayButton", Repaly)

    self.AssistantButton = self:find("AssistantButton", self.LeftTop)

    bee.addClick(self:find("ReplayCloseButton"), function()
        bee.enterScene("MainScene", {afterShow = function()
            UiManager:showUI("IngameReplay")
        end})
    end)
    bee.addClick(self.ButtonLeft, function()
        self.data:onPreAction()
        self:refreshButton()
        bee.logEvent("history-play-left", GameModel.data:getGameId())
    end)
    bee.addClick(self.ButtonRight, function()
        self.data:onNextAction()
        self:refreshButton()
        bee.logEvent("history-play-right", GameModel.data:getGameId())
    end)
    bee.addClick(self.PauseButton, function()
        self._isPuased = true
        self:refreshButton()
        bee.logEvent("history-play-pause", GameModel.data:getGameId())
    end)
    bee.addClick(self.PlayButton, function()
        if self.data:isPlayOver() then
            self.data:run()
        else
            self._isPuased = false
            self:refreshButton()
        end
    end)

    bee.addClick(self.AssistantButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("IngameAssistant", {data = GameModel.data:getRecord().msg})
        -- bee.logEvent("ingame-replay-assistant", GameModel.data:getGameType(), GameModel.data:getRoomId())
    end)
end

function P:onShow()
    self.data = self._params.data
    self._isPuased = false
    self:refreshButton()

    bee.setText(self.TextTitle, self.data.title)
    self.data:doStartAction()
end

function P:refreshButton()
    self.PauseButton:SetActive(not self._isPuased)
    self.PlayButton:SetActive(self._isPuased)

    self.ButtonLeft:SetActive(self.data:isHavePreAction())
    self.ButtonRight:SetActive(self.data:isHaveNextAction())
end

function P:refreshActor()
    local act = self.data:getAction()
    local actor = self.data:getActor()
    print("==== ggg act", json.encode(act), json.encode(actor))
    if act then
        self:showTag(act.action_type)
    else
        self:showTag()
    end
    if actor then
        bee.setTextCut(self.TextName, actor.player.name, 250)
    else
        bee.setText(self.TextName, "")
    end
    self:refreshButton()
end

function P:showTag(tag)
    if tag and POKER_ACTION_TAGS[tag] then
        bee.setText(self.TextTag, _T(POKER_ACTION_TAGS[tag].name))
        self.ImageTag:SetActive(true)
        bee.setIcon(self.ImageTag, POKER_ACTION_TAGS[tag].replayBg)
        self.TextTag:SetActive(true)
    else
        self.ImageTag:SetActive(false)
        self.TextTag:SetActive(false)
    end
end

function P:evt_recordRunAction()
    self:refreshActor()
end

function P:onUpdate(dt)
    if not self._isPuased then
        self.data:onUpdate(dt)
        if self.data:isPlayOver() then
            self._isPuased = true
            self:refreshButton()
        end
    end
end

function P:evt_gameBlur(flag, name)
    self:onUiBlur(flag, name)
end

return P