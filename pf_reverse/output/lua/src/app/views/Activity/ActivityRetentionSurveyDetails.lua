local P = class("ActivityRetentionSurveyDetails", UiDialog)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")
    self.Complete = self:find("Complete", self.Center)
    self.FillIn = self:find("FillIn", self.Center)
    self.Multiple = self:find("Multiple", self.Center)
    self.Radio = self:find("Radio", self.Center)
    self.Declaration = self:find("Declaration", self.Center)

    self.AcceptButton = self:find("AcceptButton", self.Center)
    self.DeclineButton = self:find("DeclineButton", self.Center)
    self.QueButtons = self:find("QueButtons", self.Center)
    self.NextButton = self:find("NextButton", self.QueButtons)
    self.LastButton = self:find("LastButton", self.QueButtons)
    self.FinishButton = self:find("FinishButton", self.QueButtons)

    self.sdt_quiz_button_close = self:find("sdt_quiz_button_close", self.Center)

    bee.addClick(self.sdt_quiz_button_close, function ()
        self:hideUI()
    end)
    bee.addClick(self.AcceptButton, function ()
        Game:playSound("ui_button_confirm")
        self:acceptEvent()
    end)
    bee.addClick(self.DeclineButton, function ()
        Game:playSound("ui_button_confirm")
        self:declineEvent()
    end)
    bee.addClick(self.NextButton, function ()
        Game:playSound("ui_button_confirm")
        self:nextQuestion()
    end)
    bee.addClick(self.LastButton, function ()
        Game:playSound("ui_button_confirm")
        self:lastQuestion()
    end)
    bee.addClick(self.FinishButton, function ()
        Game:playSound("ui_button_confirm")
        self:nextQuestion()
    end)

    self.questionData = ActivityModel:getQuestionData()
    self.questionList = self.questionData and self.questionData.list or {}
    table.sort(self.questionList, function (a, b)
        return a.question_id < b.question_id
    end)
    self.key = "RetentionSurveyKey" .. self.questionData.id .. LanguageManager:getLanguage() .. PlayerModel:getUid()
    self.answerData = {}
    self.curQuestion = nil
end

function P:onShow()
    self.subQueIds = {}
    for _,v in pairs(self.questionList) do
        if v.options then
            for _,ov in pairs(v.options) do
                if ov.sub then
                    for _,sv in pairs(ov.sub) do
                        table.insert(self.subQueIds, sv)
                    end
                end
            end
        end
    end

    self.answerData = LocalStore:getTableData(self.key)
    if self.answerData == nil then
        self.answerData = {datas = {}, order = {}, subs = {}}
        self:showAuthorization()
    else
        --local lastSaveData = self.answerData.datas[#self.answerData.datas]
        local data
        for _,v in pairs(self.questionList) do
            if v.question_id == self.answerData.order[#self.answerData.order] then
                data = v
                break
            end
        end
        self:showQuestion(data)
    end
end

--声明选项
function P:showAuthorization()
    self:closeAllPart()
    self.Declaration:SetActive(true)
    self.AcceptButton:SetActive(true)
    self.DeclineButton:SetActive(true)

    local contentScroll = self:find("ContentList", self.Declaration):GetComponent("ScrollRect")
    local contentText = self:find("Text", contentScroll.content):GetComponent("Text")
    local outLimit = contentText.preferredHeight > contentScroll.transform.sizeDelta.y
    contentScroll.enabled = outLimit
end
function P:acceptEvent()
    table.insert(self.answerData.order, 1)
    self:showQuestion(self.questionList[1])
end
function P:declineEvent()
    self:hideUI()
end

--展示问题
function P:showQuestion(data)
    self:closeAllPart()

    self.curQuestion = data
    self.QueButtons:SetActive(true)
    self.LastButton:SetActive(data.question_id ~= 1)
    local isLast = self:checkQuestionIsFinal()
    self.NextButton:SetActive(not isLast)
    self.FinishButton:SetActive(isLast)
    local subQue = false
    for _,v in pairs(self.answerData.subs) do
        if v.ids then
            local subKey = table.keyof(v.ids, self.curQuestion.question_id)
            if subKey ~= nil then
                subQue = true
                break
            end
        end
    end

    if data.question_type == 1 then
        --单选
        self:showRadio(data, subQue)
    elseif data.question_type == 2 then
        --多选
        self:showMultiple(data, subQue)
    elseif data.question_type == 3 then
        --填写
        self:showFillIn(data, subQue)
    end
end
--问答结束
function P:showComplete()
    self:closeAllPart()
    self.Complete:SetActive(true)
end

--单选
function P:showRadio(data, subQue)
    self.Radio:SetActive(true)
    local titleStr = self:setTitle(data.title)
    bee.setText(self:find("Title", self.Radio), titleStr)
    self:setNumber(self.Radio, data.question_id, subQue)
    local itemList = {}
    local questionRoot = self:find("Questions", self.Radio):GetComponent("ScrollRect")
    questionRoot.content.anchoredPosition = bee.v3zero
    local itemBase = self:find("Item", self.Radio)
    itemBase:SetActive(false)
    local curCount = questionRoot.content.childCount
    local dataCount = #data.options
    local answerKey = 0
    local answerData = nil
    for k,v in pairs(self.answerData.datas) do
        if v.qid == data.question_id then
            answerKey = k
            answerData = v
            break
        end
    end
    if answerData == nil then
        answerData = {qid = data.question_id, sltIndex = 0, str = ""}
        table.insert(self.answerData.datas, answerData)
        answerKey = #self.answerData.datas
    end

    for i = 1, dataCount do
        local index = i
        local item = nil
        if index <= curCount then
            item = questionRoot.content:GetChild(i - 1).gameObject
        else
            item = CU.GameObject.Instantiate(itemBase, questionRoot.content, false)
        end
        item:SetActive(true)
        local toggle = self:find("CheckToggle", item)
        local sign = self:find("CheckToggle/common_checkbox_03_fg", item)
        local content = self:find("Text", item)
        local line = self:find("Line", item)
        sign:SetActive(answerData.sltIndex == index)
        bee.addClick(toggle, function ()
            self.answerData.datas[answerKey].sltIndex = index
            for _,v in pairs(itemList) do
                self:find("CheckToggle/common_checkbox_03_fg", v):SetActive(false)
            end
            sign:SetActive(true)
        end, true)
        bee.setText(content, data.options[i].content)
        self:setOptionContent(content, item)
        self:setOptionLine(line, content, index == dataCount, data.other_option, answerData.str, answerKey)
        table.insert(itemList, item)
    end
    for i = dataCount + 1, curCount do
        local item = questionRoot.content:GetChild(i - 1)
        if item ~= nil then
            item.gameObject:SetActive(false)
        end
    end
end

--多选
function P:showMultiple(data, subQue)
    self.Multiple:SetActive(true)
    local titleStr = self:setTitle(data.title)
    bee.setText(self:find("Title", self.Multiple), titleStr)
    self:setNumber(self.Multiple, data.question_id, subQue)
    local itemList = {}
    local questionRoot = self:find("Questions", self.Multiple):GetComponent("ScrollRect")
    questionRoot.content.anchoredPosition = bee.v3zero
    local itemBase = self:find("Item", self.Multiple)
    itemBase:SetActive(false)
    local curCount = questionRoot.content.childCount
    local dataCount = #data.options
    local answerKey = 0
    local answerData = nil
    for k,v in pairs(self.answerData.datas) do
        if v.qid == data.question_id then
            answerKey = k
            answerData = v
            break
        end
    end
    if answerData == nil then
        answerData = {qid = data.question_id, sltIndexs = {}, str = ""}
        table.insert(self.answerData.datas, answerData)
        answerKey = #self.answerData.datas
    end

    for i = 1, dataCount do
        local index = i
        local item = nil
        if index <= curCount then
            item = questionRoot.content:GetChild(i - 1).gameObject
        else
            item = CU.GameObject.Instantiate(itemBase, questionRoot.content, false)
        end
        item:SetActive(true)
        local toggle = self:find("CheckToggle", item)
        local sign = self:find("CheckToggle/common_checkbox_01_fg", item)
        local content = self:find("Text", item)
        local line = self:find("Line", item)
        sign:SetActive(table.keyof(answerData.sltIndexs, index) ~= nil)
        bee.addClick(toggle, function ()
            if table.keyof(answerData.sltIndexs, index) == nil then
                table.insert(answerData.sltIndexs, index)
                sign:SetActive(true)
            else
                table.removebyvalue(answerData.sltIndexs, index)
                sign:SetActive(false)
            end
            self.answerData.datas[answerKey] = answerData
        end, true)
        bee.setText(content, data.options[i].content)
        self:setOptionContent(content, item)
        self:setOptionLine(line, content, index == dataCount, data.other_option, answerData.str, answerKey)
        table.insert(itemList, item)
    end
    for i = dataCount + 1, curCount do
        local item = questionRoot.content:GetChild(i - 1)
        if item ~= nil then
            item.gameObject:SetActive(false)
        end
    end
end

--填写
function P:showFillIn(data, subQue)
    self.FillIn:SetActive(true)
    local titleStr = self:setTitle(data.title)
    bee.setText(self:find("Title", self.FillIn), titleStr)
    self:setNumber(self.FillIn, data.question_id, subQue)
    local scrollRect = self:find("ContentList", self.FillIn):GetComponent("ScrollRect")
    local inputField = self:find("InputField", scrollRect.content):GetComponent("InputField")
    local fillKey = 0
    local fillData = nil
    for k,v in pairs(self.answerData.datas) do
        if v.qid == data.question_id then
            fillKey = k
            fillData = v
            break
        end
    end
    if fillData == nil then
        fillData = {qid = data.question_id, str = ""}
        table.insert(self.answerData.datas, fillData)
        fillKey = #self.answerData.datas
    end

    bee.setText(inputField.gameObject, fillData.str, "InputField")
    inputField.onValueChanged:AddListener(function (val)
        local height = inputField.textComponent.preferredHeight
        scrollRect.content.sizeDelta = bee.v2(scrollRect.content.sizeDelta.x, height)
        fillData.str = val
        self.answerData.datas[fillKey] = fillData
        inputField.textComponent.font = getTextFont(val, inputField.textComponent)
    end)
end

--设置选项细节
function P:setOptionContent(content, item)
    local contentText = content:GetComponent("Text")
    local height = contentText.preferredHeight
    local width = contentText.preferredWidth
    item.transform.sizeDelta = bee.v2(0, height)
    local area = self:find("CheckToggle/Area", item)
    area.transform.sizeDelta = bee.v2(width + 20, area.transform.sizeDelta.y)
end

--设置填写选项
function P:setOptionLine(line, content, isLast, isLineOption, str, key)
    if isLineOption == 0 then
        line:SetActive(false)
        return
    end
    if not isLast then
        line:SetActive(false)
        return
    end
    line:SetActive(true)
    local contentText = content:GetComponent("Text")
    local cacheWidth = contentText.preferredWidth + 66
    line.transform.anchoredPosition = bee.v2(cacheWidth, -21)
    local inputField = self:find("InputField", line):GetComponent("InputField")
    bee.setText(inputField.gameObject, str, "InputField")
    inputField.onValueChanged:AddListener(function (val)
        inputField.textComponent.font = getTextFont(val, inputField.textComponent)
        self.answerData.datas[key].str = val
    end)
end

--保存答案
function P:saveAnswer()
    LocalStore:saveTableData(self.key, self.answerData)
end
--获取下一个问题
function P:nextQuestion()
    --必答题是否有作答
    if not self:checkAnswerQuestion() then
        UiManager:showToast(_T("LAB_SURVEY_11"))
        return
    end

    local nextId = 0
    local lastId = 0 --寻找下一个id的基础id
    local over = false
    local subIds = self:getSelectedAllSubQuestions()
    if #subIds > 0 then --是否有子问题
        nextId = subIds[1]
    else
        --当前问题是否在子问题列表
        for _,v in pairs(self.answerData.subs) do
            local subKey = table.keyof(v.ids, self.curQuestion.question_id)
            if subKey ~= nil then --当前问题为子id
                if #v.ids > subKey then
                    nextId = v.ids[subKey + 1]
                    break
                else
                    lastId = v.qid
                    break
                end
            end
        end
        --回归主线问题
        if nextId == 0 then
            if lastId == 0 then
                nextId = self.curQuestion.question_id + 1
            else
                nextId = lastId + 1
            end
            local maxCount = #self.questionList
            if nextId > maxCount then
                over = true
            else
                local getNext = false
                for i = nextId, maxCount do
                    if table.keyof(self.subQueIds, i) == nil then
                        nextId = i
                        getNext = true
                        break
                    end
                end
                if not getNext then
                    over = true
                end
            end
        end
    end

    --问答结束
    if over then
        ActivityModel:submitSurveyAnswer(self.questionData.id, self.answerData.datas, self.answerData.order)
        return
    end

    local nextData = nil
    for _,v in pairs(self.questionList) do
        if v.question_id == nextId then
            nextData = v
            break
        end
    end
    table.insert(self.answerData.order, nextId)
    self:showQuestion(nextData)
    self:saveAnswer()
end
--获取上一个问题
function P:lastQuestion()
    local count = #self.answerData.order
    local lastId = self.answerData.order[count - 1]
    local lastData = nil
    for _,v in pairs(self.questionList) do
        if v.question_id == lastId then
            lastData = v
            break
        end
    end
    table.remove(self.answerData.order, count)
    self:showQuestion(lastData)
    self:saveAnswer()
end
--当前题目是否为最后题目
function P:checkQuestionIsFinal()
    local curMainLineId = 0
    --如果是子问题
    if table.keyof(self.subQueIds, self.curQuestion.question_id) ~= nil then
        for _,v in pairs(self.answerData.subs) do
            local subKey = table.keyof(v.ids, self.curQuestion.question_id)
            if subKey ~= nil then
                --拥有下一个子问题
                if #v.ids > subKey then
                    return false
                else
                    curMainLineId = v.qid
                    break
                end
            end
        end
    else
        curMainLineId = self.curQuestion.question_id
    end

    --判断下一个问题
    local nextId = curMainLineId + 1
    local maxCount = #self.questionList
    for i = nextId, maxCount do
        if table.keyof(self.subQueIds, i) == nil then
            nextId = i
            return false
        end
    end
    return true
end

--获取该题目选中选项的所有子题目id
function P:getSelectedAllSubQuestions()
    local subIds = {}
    for _,v in pairs(self.answerData.datas) do
        if v.qid == self.curQuestion.question_id then
            if self.curQuestion.question_type == 1 then
                for _,ov in pairs(self.curQuestion.options) do
                    if ov.option_id == v.sltIndex and ov.sub then
                        for _,sv in pairs(ov.sub) do
                            table.insert(subIds, sv)
                        end
                    end
                end
            elseif self.curQuestion.question_type == 2 then
                for _,ov in pairs(self.curQuestion.options) do
                    if table.keyof(v.sltIndexs, ov.option_id) ~= nil and ov.sub then
                        for _,sv in pairs(ov.sub) do
                            if table.keyof(subIds, sv) == nil then
                                table.insert(subIds, sv)
                            end
                        end
                    end
                end
                table.sort(subIds)
            end
        end
    end
    if #subIds > 0 then
        local saved = false
        for k,v in pairs(self.answerData.subs) do
            if v.qid == self.curQuestion.question_id then
                self.answerData.subs[k].ids = subIds
                saved = true
                break
            end
        end
        if not saved then
            table.insert(self.answerData.subs, {qid = self.curQuestion.question_id, ids = subIds})
        end
    end
    return subIds
end

--判定是否作答
function P:checkAnswerQuestion()
    for _,v in pairs(self.answerData.datas) do
        if v.qid == self.curQuestion.question_id then
            if self.curQuestion.required == 1 then
                if self.curQuestion.question_type == 1 and v.sltIndex == 0 then
                    return false
                end
                if self.curQuestion.question_type == 2 and #v.sltIndexs == 0 then
                    return false
                end
            end
        end
    end
    return true
end

--标题处理
function P:setTitle(titleStr)
    if LanguageManager:getLanguage() == "en" then
        return titleStr
    end

    titleStr = string.replace(titleStr, ". ", ".\u{00A0}")
    titleStr = string.replace(titleStr, "poker fate", "poker\u{00A0}fate")
    titleStr = string.replace(titleStr, "Poker Fate", "Poker\u{00A0}Fate")
    return titleStr
end

--序号处理
function P:setNumber(tran, id, isSub)
    bee.setText(self:find("Number", tran), isSub and "" or id)
end

--关闭所有子窗口
function P:closeAllPart()
    self.Complete:SetActive(false)
    self.FillIn:SetActive(false)
    self.Multiple:SetActive(false)
    self.Radio:SetActive(false)
    self.Declaration:SetActive(false)

    self.AcceptButton:SetActive(false)
    self.DeclineButton:SetActive(false)
    self.QueButtons:SetActive(false)
end

function P:evt_getQuestionRewardCallback()
    self:showComplete()
end

return P