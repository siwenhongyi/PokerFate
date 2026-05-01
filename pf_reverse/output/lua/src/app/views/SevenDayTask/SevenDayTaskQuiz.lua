local P = class("SevenDayTaskQuiz", UiFullView)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)

	self.TitleText = self:find("TitleText", Center)
	self.CloseButton = self:find("CloseButton", Center)
	self.ProgressText = self:find("Progress/ProgressText", Center)

	self.Topic1 = self:find("Topic1", Center)
	self.Topic2 = self:find("Topic2", Center)
	self.TopicImg = self:find("TopicImg", self.Topic2)
	self.AnswerTextList = self:find("AnswerTextList", Center)
	self.AnswerImgList = self:find("AnswerImgList", Center)
	self.PageLast = self:find("PageLast", Center)
	self.PageLastButton = self:find("PageLastButton", self.PageLast)
	self.PageNext = self:find("PageNext", Center)
	self.PageNextButton = self:find("PageNextButton", self.PageNext)
	self.ResultCont = self:find("ResultCont", Center)
	self.TipsText = self:find("TipsScrollView/Viewport/Content/TipsText", self.ResultCont)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)

	bee.addClick(self.PageLastButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickPageLastButton()
	end)
	bee.addClick(self.PageNextButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickPageNextButton()
	end)
end

function P:onStart()
	self._questionList = SevenDayTaskModel:getQuestionGroup(self._params.groupId)
	self._maxCount = #self._questionList
	if self._params.isReview then
		self._curIndex = 1
		self._maxIndex = self._maxCount
	else
		self._curIndex = math.min(SevenDayTaskModel:getQuestionProgressId(self._params.groupId) + 1, self._maxCount)
		self._maxIndex = self._curIndex
	end

	self:once(0.2, function()
		self:setTopicShow()
		self:setButtonShow()
	end)
end

function P:setTopicShow()
	local cfg = self._questionList[self._curIndex]

	bee.setText(self.ProgressText, _F("LAB_QUESTION_COMMON_1", self._curIndex, self._maxCount))

	-- 问题
	if cfg.question_image then
		self.Topic1:SetActive(false)
		self.Topic2:SetActive(true)
		bee.setText(self:find("TopicText", self.Topic2), _T(cfg.question_dec))
		bee.setIconInAtlas(self.TopicImg, cfg.question_image, true)
		if cfg.image_scale and cfg.image_scale[1] then
			self.TopicImg.transform.localScale = bee.v3(cfg.image_scale[1], cfg.image_scale[1], 1)
		else
			self.TopicImg.transform.localScale = bee.v3(1, 1, 1)
		end
	else
		self.Topic1:SetActive(true)
		self.Topic2:SetActive(false)
		bee.setText(self:find("TopicText", self.Topic1), _T(cfg.question_dec))
	end

	self.ResultCont:SetActive(false)

	-- 答案
	if not self._params.isReview then
		if self._curIndex < self._maxIndex or self._isFinish then
			self.ResultCont:SetActive(true)
			bee.setText(self.TipsText, _T(cfg.explain))
		end
	end

	self.AnswerImgList:SetActive(false)
	self.AnswerTextList:SetActive(false)

	-- 选项
	self._optionList = {}
	local answerList
	if cfg.answer_image_1 then
		self.AnswerImgList:SetActive(true)
		answerList = self.AnswerImgList
	else
		self.AnswerTextList:SetActive(true)
		answerList = self.AnswerTextList
	end

	for i = 1, 3 do
		local option = self:find("Option" .. i, answerList)
		self:setAnswerItem(option, cfg, i)

		bee.removeAllClick(option)
		bee.addClick(option, function()
			if self._params.isReview then
				bee.logEvent("7daytask-answer-select", 1, cfg.group, cfg.order, i)
			else
				bee.logEvent("7daytask-answer-select", 0, cfg.group, cfg.order, i)
			end

			if not self._params.isReview then
				if self._curIndex < self._maxIndex or self._isFinish then
					return
				end
			end

			self.ResultCont:SetActive(true)

			for index, item in pairs(self._optionList) do
				if index == i then
					if cfg.true_answer == i then
						self:find("Yes", item):SetActive(true)
						self:find("No", item):SetActive(false)
						bee.setText(self.TipsText, _T(cfg.explain))
						self:answerCorrect()
						Game:playSound("ui_7daytask_answer_correct")
					else
						self:find("Yes", item):SetActive(false)
						self:find("No", item):SetActive(true)
						bee.setText(self.TipsText, _T("LAB_QUESTION_COMMON_2"))
						Game:playSound("ui_7daytask_answer_wrong")
					end
				else
					self:find("Yes", item):SetActive(false)
					self:find("No", item):SetActive(false)
				end
			end
		end)
	end
end

function P:setAnswerItem(option, cfg, index)
	if not cfg["answer_text_" .. index] and not cfg["answer_image_" .. index] then
		option:SetActive(false)
		return
	end
	option:SetActive(true)
	table.insert(self._optionList, option)

	local OptionText = self:find("OptionText", option)
	local OptionImg = self:find("OptionImg", option)
	local Yes = self:find("Yes", option)
	local No = self:find("No", option)

	if cfg["answer_text_" .. index] then
		bee.setText(self:find("OptionText", option), _T("LAB_QUESTION_ANSWER_PR_" .. index) .. _T(cfg["answer_text_" .. index]))
	else
		bee.setText(self:find("OptionText", option), _T("LAB_QUESTION_ANSWER_PR_" .. index))
	end

	if OptionImg then
		bee.setIconInAtlas(self:find("OptionImg", option), cfg["answer_image_" .. index], true)
		if cfg.image_scale and cfg.image_scale[index + 1] then
			self:find("OptionImg", option).transform.localScale = bee.v3(cfg.image_scale[index + 1], cfg.image_scale[index + 1], 1)
		else
			self:find("OptionImg", option).transform.localScale = bee.v3(1, 1, 1)
		end
	end

	if not self._params.isReview then
		if self._curIndex < self._maxIndex or self._isFinish then
			Yes:SetActive(index == cfg.true_answer)
			No:SetActive(false)
		else
			Yes:SetActive(false)
			No:SetActive(false)
		end
	else
		Yes:SetActive(false)
		No:SetActive(false)
	end
end

-- 答对之后刷新按钮显示
function P:answerCorrect()
	if self._params.isReview then
		return
	end

	if self._maxIndex == self._maxCount then
		UiManager:showToast(_T("LAB_QUESTION_TIPS_1"), nil, nil, true)
		self._isFinish = true
	else
		self._maxIndex = self._maxIndex + 1
	end

	SevenDayTaskModel:sendAnswer(self._params.groupId, self._curIndex, function()
		self:setButtonShow()
	end)
end

-- 切页按钮显示
function P:setButtonShow()
	if self._curIndex > 1 then
		self.PageLast:SetActive(true)
	else
		self.PageLast:SetActive(false)
	end
	if self._curIndex < self._maxIndex then
		self.PageNext:SetActive(true)
	else
		self.PageNext:SetActive(false)
	end
end

function P:onClickPageLastButton()
	if self._curIndex <= 1 then
		return
	end
	self._curIndex = self._curIndex - 1

	self:setButtonShow()
	self:setTopicShow()
end

function P:onClickPageNextButton()
	if self._curIndex >= self._maxIndex then
		return
	end
	self._curIndex = self._curIndex + 1

	self:setButtonShow()
	self:setTopicShow()
end

return P