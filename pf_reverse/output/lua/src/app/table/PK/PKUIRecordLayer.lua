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
    self.ButtonPre = self:find("ButtonPre", Repaly)
    self.ButtonNext = self:find("ButtonNext", Repaly)
    self.PauseButton = self:find("PauseButton", Repaly)
    self.PlayButton = self:find("PlayButton", Repaly)

    self.AssistantButton = self:find("AssistantButton", self.LeftTop)
    self.SaveButton = self:find("SaveButton", self.LeftTop)

    local ReplayInfo = self:find("ReplayInfo")
    self.ingame_replay_info_bg_time = self:find('ingame_replay_info_bg_time', ReplayInfo)
    self.ingame_replay_info_bg = self:find('ingame_replay_info_bg', ReplayInfo)
    self.TextRemark = self:find("TextRemark", self.ingame_replay_info_bg_time)
    self.EditButton = self:find("EditButton", self.ingame_replay_info_bg_time)

    self.ReplayCloseButton = self:find("ReplayCloseButton")
    bee.addClick(self.ReplayCloseButton, function()
        self:onBtClose()
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
    bee.addClick(self.ButtonPre, function()
        bee.logEvent("history-play-pre", GameModel.data:getGameId())
        RecordDataModel:fetchPrevDetail(GameModel.data:getGameId(), GameModel.data:getRecord().listType, function(ok, detailData, adjacentGameid, hasMore)
            if ok then
                UiManager:showUI("LoadingLayer", {cb = function()
                    local data = require("app.table.data.PKRecordData"):create(detailData)
                    data.listType = GameModel.data:getRecord().listType
                    data:run()
                end})
            end
        end)
    end)
    bee.addClick(self.ButtonNext, function()
        bee.logEvent("history-play-next", GameModel.data:getGameId())
        RecordDataModel:fetchNextDetail(GameModel.data:getGameId(), GameModel.data:getRecord().listType, function(ok, detailData, adjacentGameid, hasMore)
            if ok then
                UiManager:showUI("LoadingLayer", {cb = function()
                    local data = require("app.table.data.PKRecordData"):create(detailData)
                    data.listType = GameModel.data:getRecord().listType
                    data:run()
                end})
            end
        end)
    end)

    bee.addClick(self.AssistantButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("IngameAssistant", {data = GameModel.data:getRecord().msg})
        -- bee.logEvent("ingame-replay-assistant", GameModel.data:getGameType(), GameModel.data:getRoomId())
    end)
    
    bee.addClick(self.EditButton, function()
        UiManager:showUI("IngameReplayEdit", {data = RecordDataModel:findRecord(GameModel.data:getGameId()), scheme = GameModel.data:getIngameScheme()})
    end)
    
    if self.SaveButton then
        bee.addClick(self.SaveButton, function()
            local data = RecordDataModel:findRecord(GameModel.data:getGameId())
            if not data.collected and PlayerModel:getCurRecord() >= PlayerModel:getRecordNum() then
                GameModel:saveReplay(GameModel.data:getGameId(), function(ok)
                    if ok then
                        self:refreshCollected()
                        UiManager:showToast(_T("LAB_SAVE_GAME_TIP3"))
                    end
                end)
                return
            end
            self:onBtSaveClick()
        end)
    end
end

function P:onShow()
    self.data = self._params.data
    self._isPuased = false
    self:refreshButton()
    self:evt_ReplayRemarkChanged()

    bee.setText(self.TextTitle, self.data.title)
    self.data:doStartAction()

    local data = RecordDataModel:findRecord(GameModel.data:getGameId()) or {}
    self:find("Off", self.SaveButton):SetActive(data.collected)
    self:find("On", self.SaveButton):SetActive(not data.collected)
    self:refreshCollected()

    self.ButtonPre:SetActive(RecordDataModel:hasPrevDetail(GameModel.data:getGameId(), GameModel.data:getRecord().listType))
    self.ButtonNext:SetActive(RecordDataModel:hasNextDetail(GameModel.data:getGameId(), GameModel.data:getRecord().listType))
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
        bee.setTextCut(self.TextName, GF.getOtherName(actor.player.name, actor.seatid + 1, actor.uid), 250)
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

function P:refreshCollected()
    local data = RecordDataModel:findRecord(GameModel.data:getGameId()) or {}
    self.ingame_replay_info_bg_time:SetActive(data.collected)
    self.ingame_replay_info_bg:SetActive(not data.collected)

    self:find("Off", self.SaveButton):SetActive(data.collected)
    self:find("On", self.SaveButton):SetActive(not data.collected)
end

function P:onBtSaveClick()
    if not bee.checkCd("recordlayer_onBtSaveClick", 2) then
        return
    end
    local flag = self:find("Off", self.SaveButton).activeSelf
    self:find("Off", self.SaveButton):SetActive(not flag)
    self:find("On", self.SaveButton):SetActive(flag)
    if flag then
        RecordDataModel:removeCollect(GameModel.data:getGameId(), function(ok)
            if ok then
                self:refreshCollected()
                UiManager:showToast(_T("LAB_GAME_088"))
            end
        end)
    else
        RecordDataModel:addCollect(GameModel.data:getGameId(), function(ok)
            if ok then
                self:refreshCollected()
                UiManager:showToast(_T("LAB_SAVE_GAME_TIP3"))
            end
        end)
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

function P:evt_ReplayRemarkChanged()
    local data = RecordDataModel:findRecord(GameModel.data:getGameId())
    if data and data.remark and data.remark ~= "" then
        bee.setText(self.TextRemark, data.remark)
    else
        bee.setText(self.TextRemark, _T("LAB_GAME_081"))
    end
end

function P:onBtClose()
    bee.enterScene("MainScene", {afterShow = function()
        UiManager:showUI("IngameReplay", {record = true})
    end})
end

return P