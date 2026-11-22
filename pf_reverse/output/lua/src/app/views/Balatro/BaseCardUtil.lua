local P = {
    --卡牌动画列表
    AniStateTagDic = {},

    --点击抬高距离
    clickPos = 20,
    --点击抬高动画时长
    clickAniTime = 0.06,
    --卡牌说明
    explainItem = nil,
    --按钮偏移值
    btnDifPos = 125,

    --长按拖动时卡牌列表
    dragingCardList = {},
    --长按拖动时卡牌位置列表
    dragingCardPosList = {},
    --拖动差值
    dragDelta = nil,
    dragScale = 1,

}
BaseCardUtil = P

--通用切换卡牌选中状态功能
function P:SwitchCardSelecting(card, click)
    card.selecting = not card.selecting
    if card.selecting then
        if click then
            Game:playSound("ui_button_confirm")
        end
        self:PlayAniState(card.ani, Bal.BaseCardAni.xuanzhong, true)
        self:selectUpEx(card)
        -- CardInfoModel:OpenCardInfo(card, OpenCardPos.Battle) 卡牌描述
    else
        if click then
            Game:playSound("ui_button_confirm")
        end
        self:PlayAniState(card.ani, Bal.BaseCardAni.xuanzhongchehui, true)
        self:selectDownEx(card)
    end
end
function P:CardTweenEvent(card, strPos, endPos, action)
    bee.tween():toFloat(strPos, endPos, self.clickAniTime, function(v)
        card.tran.anchoredPosition = bee.v2(card.tran.anchoredPosition.x , v)
    end):onComplete(function()
        if action ~= nil then
            action()
        end
    end)
end
--重置卡牌到原始状态
function P:resetCardState(item)
    item.selecting = false
end

--卡牌动画
function P:PlayAniState(animator, stateName, restart, action)
    local tag = self.AniStateTagDic[animator]
    if tag ~= nil then
        if restart then
            scheduler:removeTag(tag)
            self.AniStateTagDic[animator] = nil
        else
            return
        end
    end
    animator:Play(stateName, -1, 0)

    local time = 0
    local clips = animator.runtimeAnimatorController.animationClips
    for i = 1, clips.Length do
        if clips[i - 1].name == stateName then
            time = clips[i - 1].length
        end
    end

    time = time + 0.1
    local schedul = bee.once(time, function()
        -- CS_BattleUtil.SetAnimationLastFrame(animator, stateName)
        -- if not animator.isPlaying then
        --     animator:Play(stateName)
        -- end
        -- local state = animator[stateName]
        -- if state then
        --     state.time = state.length
        --     animator:Sample()
        -- end

        self.AniStateTagDic[animator] = nil
        if action then
            action()
        end
    end)
    self.AniStateTagDic[animator] = schedul
    return schedul
end

--清除卡牌动画
function P:ClearAniStateTag(animator)
    if self.AniStateTagDic[animator] == nil then
        return
    end
    animator:Stop()
    scheduler:removeTag(self.AniStateTagDic[animator])
    self.AniStateTagDic[animator] = nil
end

--是否完成播放
function P:isPlayOver(animator, stateName)
    if bee.isNull(animator) or not stateName then
        return false
    end

    local stateInfo = animator:GetCurrentAnimatorStateInfo(0)
    if stateInfo.shortNameHash == CS.UnityEngine.Animator.StringToHash(stateName) then
        return not stateInfo.loop and stateInfo.normalizedTime >= 1
    end
    return true
end

--删除扑克动画
function P:DeletePokerAni(poker)
    local aniStr = Bal.BaseCardAni.qipai
    local randomNum = math.random(0, 3)
    if randomNum > 0 then
        aniStr = aniStr .. (randomNum + 1)
    end
    
    -- self:ClearCardIdleTag(poker)
    self:PlayAniState(poker.ani, aniStr, true, function()
        self:recoveryCard(poker)
    end)
end

--选中提高
function P:selectUpEx(card)
    card.Center.transform.localPosition = bee.v3(0, 11, 0)
    bee.tween():toFloat(11, 43, 0.2, function(v)
        card.Center.transform.localPosition = bee.v3(0, v, 0)
    end)
end
--选中回落
function P:selectDownEx(card)
    bee.tween():toFloat(43, 0, 0.2, function(v)
        card.Center.transform.localPosition = bee.v3(0, v, 0)
    end)
end


--回收卡牌
function P:recoveryCard(card)
    CU.GameObject.Destroy(card.node)
end

-- function P:checkMove(joker, jokerList, posList)
-- end



--通用牌动画名
Bal.BaseCardAni = {
    fapai = 'BalatroCard_fapai',
    xuanzhong = 'BalatroCard_xuanzhong',
    xuanzhongchehui = 'BalatroCard_xuanzhong_chehui',
    changan = 'BalatroCard_changan',
    chupai = 'BalatroCard_chupai',
    qipai = 'BalatroCard_qipai',
    jiafen = 'BalatroCard_jiafen',
    daiji = 'BalatroCard_daiji',

    huanpaizuo = 'BalatroCard_huanpai_zuo',
    huanpaiyou = 'BalatroCard_huanpai_you',
    paixuzuo = 'BalatroCard_paixu_zuo',
    paixuyou = 'BalatroCard_paixu_you',

----
    chupaijieshu = 'BaseCard_chupai_end',

    fanpai = 'BaseCard_fanpai',
    fanpaifanhui = 'BaseCard_fanpai_fanhui',
    shoupai = 'BaseCard_shoupai',

    chuxian = 'BaseCard_chuxian_jiemian',
    kabaokachuxian = 'BaseCard_chuxian',
    rongjie = 'BaseCard_doudongrongjie',
    
}

return P