local P = class("BalatroBaseCard", Object)
BalatroBaseCard = P

function P:onAwake()
    self.data = nil
    self.index = 0
    self.longPress = false
    self.draging = false
    self.selecting = false

    self.AnimRoot = self:find("AnimRoot").transform
    self.ani = self.AnimRoot:GetComponent("Animator")
    self.Root = self:find("Root", self.AnimRoot)
    self.Back = self:find("Back", self.Root)
    self.Icon = self:find("Icon", self.Root)

    self.btn = self.node:GetComponent("EventTriggerListener")
    self:buttonDownEx()
end

function P:setData(data)
    self.data = data
    self:setCardBack()
    self:setPokerIcon(data.suit, data.point)
end

--牌背
function P:setCardBack()
    local cardBackImage = DecorationModel:getCurCardBackImage(BalBattleModel:getScheme()) or nil
    bee.setIcon(self.Back, cardBackImage)
end

--牌面
function P:setPokerIcon(suit, point)
    self.Icon:SetActive(true)

    local scheme = BalBattleModel:getScheme()
    local mapId = tpl_props[scheme.card_front].mapId
    local ImagePath = string.format("Card[" .. tpl_card[mapId].image .."_%s_%s]", Config.CARD_COLOR_2_STRING[suit], Config.CARD_NUM_2_STRING[Bal.PokerScore[point]])
    bee.setIcon(self.Icon, ImagePath)
end

--角色
-- function P:setRole(characterId)
--     self.Icon:SetActive(false)
--     self.Role:SetActive(true)

--     local cfg = tpl_character_skin[characterId]
--     bee.setIcon(self.RoleIcon, cfg.image, true)
--     self.RoleIcon.transform.localPosition = bee.v3(cfg.leaderboard_offset[1], cfg.leaderboard_offset[2], 0)
--     self.RoleIcon.transform.localScale = bee.v3(cfg.leaderboard_offset[3], cfg.leaderboard_offset[3], 1)
    
--     if cfg.spine_rotation then
--         self.RoleIcon.transform.localEulerAngles = bee.v3(0, 0, cfg.spine_rotation)
--     else
--         self.RoleIcon.transform.localEulerAngles = bee.v3zero
--     end
-- end

--选中提高
function P:selectUpEx()
    self.Root.transform.localPosition = bee.v3(0, 11, 0)
    bee.tween():toFloat(11, 43, 0.2, function(v)
        self.Root.transform.localPosition = bee.v3(0, v, 0)
    end)
end
--选中回落
function P:selectDownEx()
    bee.tween():toFloat(43, 0, 0.2, function(v)
        self.Root.transform.localPosition = bee.v3(0, v, 0)
    end)
end

--按钮事件拓展
function P:buttonDownEx()
    self.btn.onDown:AddListener(function (_, eventData)
        if self._buttonExReleaseTag then
            scheduler:removeTag(self._buttonExReleaseTag)
        end

        local pointerId = eventData.pointerId
        self._buttonExReleaseTag = bee.loopTimer(0, 0.01, function ()
            local isPointerHeld = false
            if pointerId >= 0 then
                for i = 0, CU.Input.touchCount - 1 do
                    local touch = CU.Input.GetTouch(i)
                    if touch.fingerId == pointerId then
                        isPointerHeld = touch.phase ~= CU.TouchPhase.Ended
                            and touch.phase ~= CU.TouchPhase.Canceled
                        break
                    end
                end
            else
                local mouseButton = pointerId == -2 and 1 or pointerId == -3 and 2 or 0
                isPointerHeld = CU.Input.GetMouseButton(mouseButton)
            end

            if isPointerHeld then
                return
            end

            local releaseTag = self._buttonExReleaseTag
            self._buttonExReleaseTag = nil
            scheduler:removeTag(releaseTag)

            if self.longPress and not self.draging then
                self.btn.onUp:Invoke(self.node, eventData)
            end
        end, self.node)
    end)
end

return P