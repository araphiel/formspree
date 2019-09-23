/** @format */

const React = require('react')

import ajax from '../ajax'
import {LoadingContext} from '../Dashboard'
import LoaderButton from '../components/LoaderButton'

class Card extends React.Component {
  constructor(props) {
    super(props)

    this.makeCardDefault = this.makeCardDefault.bind(this)
    this.deleteCard = this.deleteCard.bind(this)
  }

  render() {
    const {card, onCardClicked, isOpen} = this.props

    return (
      <>
        <tr onClick={onCardClicked}>
          <td>
            <div className="arrow">
              <i
                className={`ion-chevron-${isOpen ? 'down' : 'right'}`}
                aria-hidden="true"
              />
            </div>
          </td>
          <td>
            <i className={`fa fa-${card.css_name}`} aria-hidden="true" />
          </td>
          <td>
            ••••
            {card.last4}
          </td>
          <td>
            {card.exp_month}/{card.exp_year}
          </td>
        </tr>
        <tr className={isOpen ? '' : 'hidden'}>
          <td colSpan="4">
            <div
              className="actions"
              style={{
                float: 'right',
                width: '50%',
                paddingLeft: '20%'
              }}
            >
              {card.default ? (
                <p>
                  <button
                    style={{
                      color: 'white',
                      backgroundColor: '#359173',
                      border: 'none'
                    }}
                    className="disabled"
                    disabled
                  >
                    Default
                  </button>
                </p>
              ) : (
                <LoaderButton
                  onClick={this.makeCardDefault}
                  data-card-id={card.id}
                  style={{marginBottom: '18px'}}
                >
                  Make Default
                </LoaderButton>
              )}
              <LoaderButton onClick={this.deleteCard} data-card-id={card.id}>
                Delete
              </LoaderButton>
            </div>
            <div>
              <p>
                Number: ••••
                {card.last4}
              </p>
              <p>
                Type: {card.brand} {card.funding} card
              </p>
              <p>
                Origin: {card.country}{' '}
                <img
                  src={`/static/img/countries/${card.country.toLowerCase()}.png`}
                  width="25"
                />
              </p>
              <p>
                CVC Check:{' '}
                {card.cvc_check === 'pass' ? (
                  <>
                    Passed{' '}
                    <i className="fa fa-check-circle-o" aria-hidden="true" />
                  </>
                ) : card.cvc_check === 'fail' ? (
                  <>
                    Failed
                    <i className="fa fa-times-circle-o" aria-hidden="true" />
                  </>
                ) : (
                  <>
                    Unknown
                    <i className="fa fa-question-circle" aria-hidden="true" />
                  </>
                )}
              </p>
            </div>
          </td>
        </tr>
      </>
    )
  }

  async makeCardDefault(e) {
    e.preventDefault()
    let cardId = e.target.dataset.cardId

    await ajax({
      endpoint: `/api-int/account/cards/${cardId}/default`,
      method: 'PUT',
      errorMsg: 'Failed to change default card',
      successMsg: 'Default card changed successfully.',
      onSuccess: this.props.onCardChanged
    })

    this.props.ready()
  }

  async deleteCard(e) {
    e.preventDefault()
    let cardId = e.target.dataset.cardId

    await ajax({
      endpoint: `/api-int/account/cards/${cardId}`,
      method: 'DELETE',
      errorMsg: 'Failed to delete card',
      successMsg: 'Card deleted successfully.',
      onSuccess: this.props.onCardChanged
    })

    this.props.ready()
  }
}

export default props => (
  <LoadingContext.Consumer>
    {({ready}) => <Card {...props} ready={ready} />}
  </LoadingContext.Consumer>
)
